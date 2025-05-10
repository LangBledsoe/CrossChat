package function

import (
	"crypto/ed25519"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"io/ioutil"
	"bytes"

	"github.com/GoogleCloudPlatform/functions-framework-go/functions"
)

// Discord interaction types
const (
	INTERACTION_PING                = 1
	INTERACTION_APPLICATION_COMMAND = 2
	INTERACTION_MESSAGE_COMPONENT   = 3
	INTERACTION_MODAL_SUBMIT        = 5
)

// Discord response types
const (
	RESPONSE_PONG            = 1
	RESPONSE_CHANNEL_MESSAGE = 4
	RESPONSE_DEFERRED_MESSAGE = 5
	RESPONSE_UPDATE_MESSAGE   = 7
	RESPONSE_MODAL            = 9
)

// Zero-width character mappings for encoding/decoding
var encodeMap = map[rune]string{
	'0': "\u200b", // zero-width space
	'1': "\u200c", // zero-width non-joiner
	'2': "\u200d", // zero-width joiner
	'3': "\u2060", // word joiner
	'4': "\u2061", // function application
	'5': "\u2062", // invisible times
	'6': "\u2063", // invisible separator
	'7': "\u2064", // invisible plus
	'8': "\u206a", // inhibit symmetric swapping
	'9': "\u206b", // activate symmetric swapping
}

var decodeMap = map[rune]string{
	'\u200b': "0",
	'\u200c': "1",
	'\u200d': "2",
	'\u2060': "3",
	'\u2061': "4",
	'\u2062': "5",
	'\u2063': "6",
	'\u2064': "7",
	'\u206a': "8",
	'\u206b': "9",
}

// ZERO_WIDTH_MARKER to easily find encoded sender_id
const ZERO_WIDTH_MARKER = "\u200b\u200b\u200b"

// DiscordResponse represents the response structure for Discord
type DiscordResponse struct {
	Type int                    `json:"type"`
	Data map[string]interface{} `json:"data,omitempty"`
}

// Interaction represents the base Discord interaction payload
type Interaction struct {
	Type int             `json:"type"`
	Data json.RawMessage `json:"data,omitempty"`
	Member *struct {
		User *DiscordUser `json:"user,omitempty"`
	} `json:"member,omitempty"`
	User *DiscordUser `json:"user,omitempty"`
}

// DiscordUser represents a Discord user object
type DiscordUser struct {
	ID       string `json:"id"`
	Username string `json:"username"`
}

// ApplicationCommandInteractionData represents the data for an application command interaction
type ApplicationCommandInteractionData struct {
	Resolved struct {
		Messages map[string]DiscordMessage `json:"messages,omitempty"`
	} `json:"resolved,omitempty"`
}

// DiscordMessage represents a Discord message object
type DiscordMessage struct {
	Content string `json:"content"`
}

// ModalInteractionData represents the data for a modal submit interaction
type ModalInteractionData struct {
	CustomID   string `json:"custom_id"`
	Components []struct {
		Type       int `json:"type"`
		Components []struct {
			Type     int    `json:"type"`
			CustomID string `json:"custom_id"`
			Value    string `json:"value"`
		} `json:"components,omitempty"`
	} `json:"components,omitempty"`
}

type Secrets struct {
    AccessToken         string   `json:"INSTAGRAM_ACCESS_TOKEN"`
    DiscordPublicKey    string   `json:"DISCORD_PUBLIC_KEY"`
}

var secrets Secrets

func loadSecrets(filePath string) {
    data, err := ioutil.ReadFile(filePath)
    if err != nil {
        log.Fatalf("Error: Secret file not found at %s: %v", filePath, err)
    }
    if err := json.Unmarshal(data, &secrets); err != nil {
        log.Fatalf("Error: Could not decode JSON from %s: %v", filePath, err)
    }
    log.Println("Successfully loaded secrets from file.")
}

func init() {
    loadSecrets("/etc/secrets/mysecrets.json")
    functions.HTTP("DiscordHandler", discordHandler)
    log.Printf("Discord handler initialized with Instagram DM functionality")
}

// discordHandler is the entry point for the Cloud Function
func discordHandler(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	log.Printf("Received request: %s", r.Method)

	if os.Getenv("SKIP_DISCORD_VERIFICATION") != "true" {
		if !verifyDiscordSignature(body, r.Header.Get("X-Signature-Ed25519"), r.Header.Get("X-Signature-Timestamp")) {
			log.Println("Failed to verify Discord signature")
			http.Error(w, "Invalid signature", http.StatusUnauthorized)
			return
		}
	} else {
		log.Println("Skipping Discord signature verification")
	}

	var interaction Interaction
	if err := json.Unmarshal(body, &interaction); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	switch interaction.Type {
	case INTERACTION_PING:
		respondWithPong(w)
	case INTERACTION_APPLICATION_COMMAND:
		handleApplicationCommand(w, body, interaction)
	case INTERACTION_MODAL_SUBMIT:
		handleModalSubmit(w, body, interaction)
	default:
		respondWithPong(w)
	}
}

func respondWithPong(w http.ResponseWriter) {
	response := DiscordResponse{Type: RESPONSE_PONG}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func handleApplicationCommand(w http.ResponseWriter, rawBody []byte, interaction Interaction) {
	var data ApplicationCommandInteractionData
	if err := json.Unmarshal(interaction.Data, &data); err != nil {
		log.Printf("Error unmarshalling application command data: %v", err)
		http.Error(w, "Invalid application command data", http.StatusBadRequest)
		return
	}

	if len(data.Resolved.Messages) > 0 {
		var referencedMessage DiscordMessage
		for _, msg := range data.Resolved.Messages {
			referencedMessage = msg
			break // Take the first one
		}
		recipientID := decodeInvisible(referencedMessage.Content)
		if recipientID != "" {
			openDMModal(w, recipientID)
			return
		} else {
			respondWithMessage(w, "⚠️ You must respond to a message that was sent by an Instagram user")
			return
		}
	} else {
		respondWithMessage(w, "⚠️ You must respond to a message that was sent by an Instagram user")
		return
	}
}

func handleModalSubmit(w http.ResponseWriter, rawBody []byte, interaction Interaction) {
	var data ModalInteractionData
	if err := json.Unmarshal(interaction.Data, &data); err != nil {
		log.Printf("Error unmarshalling modal submit data: %v", err)
		http.Error(w, "Invalid modal submit data", http.StatusBadRequest)
		return
	}

	if strings.HasPrefix(data.CustomID, "instamsg_modal_") {
		recipientID := strings.TrimPrefix(data.CustomID, "instamsg_modal_")
		var dmText string
		for _, row := range data.Components {
			for _, comp := range row.Components {
				if comp.CustomID == "dm_text" {
					dmText = comp.Value
					break
				}
			}
			if dmText != "" {
				break
			}
		}

		if dmText == "" {
			respondWithMessage(w, "No message provided.")
			return
		}

		var discordUsername string
		if interaction.Member != nil && interaction.Member.User != nil {
			discordUsername = interaction.Member.User.Username
		} else if interaction.User != nil {
			discordUsername = interaction.User.Username
		}

		messageToSend := dmText
		if discordUsername != "" {
			messageToSend = fmt.Sprintf("%s: %s", discordUsername, dmText)
		}

		log.Printf("Sending Instagram message to %s: %s", recipientID, messageToSend)

		success, response := sendInstagramMessage(recipientID, messageToSend)

		if success {
			respondWithMessage(w, fmt.Sprintf("Message sent: %s", dmText))
		} else {
			respondWithMessage(w, fmt.Sprintf("Failed to send message: %s. Error: %s", dmText, response))
		}
		return
	}

	respondWithMessage(w, "Invalid modal context.")
}

func openDMModal(w http.ResponseWriter, recipientID string) {
	response := DiscordResponse{
		Type: RESPONSE_MODAL,
		Data: map[string]interface{}{
			"custom_id": fmt.Sprintf("instamsg_modal_%s", recipientID),
			"title":     "Send Instagram DM",
			"components": []map[string]interface{}{
				{
					"type": 1, // ACTION_ROW
					"components": []map[string]interface{}{
						{
							"type":        4, // TEXT_INPUT
							"custom_id":   "dm_text",
							"style":       2, // PARAGRAPH (multi-line)
							"label":       "Message to send",
							"min_length":  1,
							"max_length":  2000,
							"placeholder": "Type your Instagram DM here...",
							"required":    true,
						},
					},
				},
			},
		},
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func respondWithMessage(w http.ResponseWriter, content string) {
	response := DiscordResponse{
		Type: RESPONSE_CHANNEL_MESSAGE,
		Data: map[string]interface{}{
			"content": content,
		},
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func verifyDiscordSignature(body []byte, signature, timestamp string) bool {
	if signature == "" || timestamp == "" {
		log.Println("Missing signature or timestamp")
		return false
	}

	message := timestamp + string(body)

	publicKeyBytes, err := hex.DecodeString(secrets.DiscordPublicKey)
	if err != nil {
		log.Println("Error decoding public key:", err)
		return false
	}
	publicKey := ed25519.PublicKey(publicKeyBytes)

	signatureBytes, err := hex.DecodeString(signature)
	if err != nil {
		log.Println("Error decoding signature:", err)
		return false
	}

	if !ed25519.Verify(publicKey, []byte(message), signatureBytes) {
		log.Println("Invalid signature")
		return false
	}

	return true
}

// decodeInvisible decodes a string containing zero-width characters to extract a user ID
func decodeInvisible(s string) string {
	idx := strings.Index(s, ZERO_WIDTH_MARKER)
	if idx == -1 {
		return ""
	}
	encodedPart := s[idx+len(ZERO_WIDTH_MARKER):]
	var decodedIDBuilder strings.Builder
	for _, r := range encodedPart {
		if val, ok := decodeMap[r]; ok {
			decodedIDBuilder.WriteString(val)
		} else {
			break // Stop at the first non-zero-width character
		}
	}
	return decodedIDBuilder.String()
}


func sendInstagramMessage(recipientID string, message string) (bool, string) {
	accessToken := secrets.AccessToken

	url := "https://graph.instagram.com/v12.0/me/messages"
	params := fmt.Sprintf("?access_token=%s", accessToken)

	// Define the request payload
	payload := map[string]interface{}{
		"recipient": map[string]string{
			"id": recipientID,
		},
		"message": map[string]string{
			"text": message,
		},
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return false, "Failed to marshal JSON"
	}

	// Make the POST request
	resp, err := http.Post(url+params, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return false, fmt.Sprintf("Request error: %v", err)
	}
	defer resp.Body.Close()

	body, _ := ioutil.ReadAll(resp.Body)

	if resp.StatusCode == http.StatusOK {
		return true, string(body)
	}
	return false, string(body)
}