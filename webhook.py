import os
import discord
import threading
import time
import re
from flask import Flask, request, jsonify
import grequests
import logging
import requests
from pathlib import Path
from gevent import monkey
from collections import deque
import json
monkey.patch_all()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_secrets_from_file(file_path="/etc/secrets/mysecrets.json"):
    """
    Reads secrets from a JSON file mounted by Cloud Run Secret Manager.

    Args:
        file_path (str): The path to the mounted secrets file.
                         Defaults to "/etc/secrets/mysecrets.json".

    Returns:
        dict: A dictionary containing the loaded secrets, or None if an error occurs.
    """
    try:
        with open(file_path, 'r') as f:
            secrets = json.load(f)
            return secrets
    except FileNotFoundError:
        print(f"Error: Secret file not found at {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}")
        return None


secrets = get_secrets_from_file()

if secrets:
    DISCORD_BOT_TOKEN = secrets.get("DISCORD_BOT_TOKEN")
    DISCORD_CHANNEL_ID = secrets.get("DISCORD_CHANNEL_ID")
    INSTAGRAM_BOT_USER_ID = secrets.get("INSTAGRAM_BOT_USER_ID")
    INSTAGRAM_ACCESS_TOKEN = secrets.get("INSTAGRAM_ACCESS_TOKEN")
    VERIFY_TOKEN = secrets.get("VERIFY_TOKEN")
    DISCORD_USER_IDS = secrets.get("DISCORD_USER_IDS")

    logger.info("Successfully loaded secrets from file.")
else:
    logger.error("Failed to load secrets from file. Application may not function correctly.")

# Constants
MAX_DISCORD_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# Thread-safe queue for pending reels/posts
pending_reels = deque()
pending_reels_lock = threading.Lock()
timer_running = False

# Discord client management
is_discord_client_running = False
discord_client_lock = threading.Lock()


# Function to verify webhook (for Instagram)
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verifies the webhook subscription by responding to Instagram's challenge request."""
    challenge = request.args.get('hub.challenge')
    verify_token = request.args.get('hub.verify_token')

    if verify_token == VERIFY_TOKEN:
        return challenge
    else:
        return 'Verification failed', 403


def get_instagram_username(sender_id):
    """Safely retrieve Instagram username from sender ID."""
    try:
        url = f"https://graph.instagram.com/{sender_id}?fields=username&access_token={INSTAGRAM_ACCESS_TOKEN}"
        req = grequests.get(url)
        response = grequests.map([req])[0]
        if response and response.status_code == 200:
            return response.json().get('username', 'Unknown User')
        return 'Unknown User'
    except Exception as e:
        logger.error(f"Error getting username: {e}")
        return 'Unknown User'


def download_reel(url, media_type="reel"):
    """
    Downloads a reel or post and returns the path if size is under 10MB, otherwise returns None.
    Returns: (file_path, file_size) or (None, None) if download failed or file too large
    """
    try:
        # Create a temporary directory for downloads
        temp_dir = Path("/tmp/reels")
        temp_dir.mkdir(exist_ok=True)

        # Determine extension and filename based on media_type
        ext = ".mp4"
        if media_type == "post":
            ext = None
            for possible in [".jpg", ".jpeg", ".png"]:
                if url.lower().endswith(possible):
                    ext = possible
                    break
            if not ext:
                ext = ".jpg"
        temp_file = temp_dir / f"reel_{threading.get_ident()}{ext}"

        # Check if the URL is reachable before downloading (avoid 404/private content)
        head_response = requests.head(url, allow_redirects=True)
        if head_response.status_code == 404:
            logger.info(f"{media_type.capitalize()} URL returned 404 (likely private/deleted): {url}")
            return None, None
        elif head_response.status_code != 200:
            logger.error(f"{media_type.capitalize()} URL returned status {head_response.status_code}: {url}")
            return None, None

        # Stream the download to check size
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            logger.error(f"Failed to download {media_type}. Status code: {response.status_code}")
            return None, None

        # Get content length if available
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) >= MAX_DISCORD_FILE_SIZE:
            logger.info(f"{media_type.capitalize()} too large: {int(content_length)} bytes")
            return None, int(content_length)

        # Download the file while checking size
        total_size = 0
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                total_size += len(chunk)
                if total_size >= MAX_DISCORD_FILE_SIZE:
                    f.close()
                    temp_file.unlink()  # Delete the partial file
                    logger.info(f"{media_type.capitalize()} too large: {total_size} bytes")
                    return None, total_size
                f.write(chunk)

        return str(temp_file), total_size
    except Exception as e:
        logger.error(f"Error downloading {media_type}: {str(e)}")
        if 'temp_file' in locals() and temp_file.exists():
            temp_file.unlink()
        return None, None


# === Zero-width encoding utilities ===
def encode_invisible(text):
    mapping = {
        '0': '\u200b',  # zero-width space
        '1': '\u200c',  # zero-width non-joiner
        '2': '\u200d',  # zero-width joiner
        '3': '\u2060',  # word joiner
        '4': '\u2061',  # function application
        '5': '\u2062',  # invisible times
        '6': '\u2063',  # invisible separator
        '7': '\u2064',  # invisible plus
        '8': '\u206a',  # inhibit symmetric swapping
        '9': '\u206b',  # activate symmetric swapping
    }
    return ''.join(mapping[d] for d in str(text) if d in mapping)


# A marker to find the encoded sender_id easily
ZERO_WIDTH_MARKER = '\u200b\u200b\u200b'  # 3x zero-width space


def parse_mentions(message_text):
    """
    Parse message text for @mentions and replace them with Discord mention format <@USER_ID>
    Args:
        message_text (str): The message text to parse
    Returns:
        str: The message text with @mentions replaced with Discord mention format
    """
    if not message_text:
        return message_text

    # Regular expression to find @username mentions
    mention_pattern = r'@(\w+)'

    def replace_mention(match):
        username = match.group(1)
        # Check if username is in the DISCORD_USER_IDS dictionary
        if username in DISCORD_USER_IDS:
            # Replace with Discord mention format <@USER_ID>
            return f"<@{DISCORD_USER_IDS[username]}>"
        # If not found, return the original @username
        return match.group(0)

    # Replace all @mentions in the message
    return re.sub(mention_pattern, replace_mention, message_text)


@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handles incoming webhook events from Instagram and sends human-readable messages to Discord."""
    global timer_running
    try:
        data = request.get_json()

        # Extract relevant data
        messaging = data['entry'][0]['messaging'][0]
        sender_id = messaging['sender']['id']

        # Get username
        username = get_instagram_username(sender_id)

        # Initialize message variables
        message_text = None
        reel_url = None
        media_type = None

        # Skip if the message is from our bot
        if sender_id == str(INSTAGRAM_BOT_USER_ID):
            return jsonify({'status': 'skipped bot message'}), 200

        # Extract message content and reel URL if present
        is_supported = False
        if 'message' in messaging:
            message = messaging['message']
            message_text = message.get('text', '')

            if 'attachments' in message:
                for attachment in message['attachments']:
                    if attachment['type'] == 'ig_reel':
                        reel_url = attachment['payload']['url']
                        media_type = "reel"
                        is_supported = True
                    elif attachment['type'] == 'share':
                        reel_url = attachment['payload']['url']
                        media_type = "post"
                        is_supported = True

        # If we have a message_text but no attachments (text only), allow
        if message_text and not media_type:
            is_supported = True

        # If it's not a supported type, do not send anything
        if not is_supported:
            logger.info(f"Unsupported message type from {username}, skipping send.")
            return jsonify({'status': 'unsupported type, skipped'}), 200

        # Handle reel/post logic
        if reel_url:
            # Find the most recent pending reel for this sender (if any)
            current_pending_reel = None
            with pending_reels_lock:
                for reel in pending_reels:
                    if reel['sender_id'] == sender_id:
                        current_pending_reel = reel
                        break

            if current_pending_reel:
                # If there's already a pending reel from this sender and we got a message text,
                # update that reel with the message text
                if message_text:
                    with pending_reels_lock:
                        pending_reels.remove(current_pending_reel)
                        send_message_to_discord(
                            username=current_pending_reel['username'],
                            message_text=message_text,
                            reel_url=current_pending_reel['url'],
                            media_type=current_pending_reel['media_type'],
                            sender_id=current_pending_reel['sender_id']
                        )
                    return jsonify({'status': 'sent with text'}), 200

            # Add the new reel to the queue
            new_reel = {
                'url': reel_url,
                'username': username,
                'media_type': media_type,
                'sender_id': sender_id,
                'message_text': None,
                'timestamp': threading.Event()
            }

            with pending_reels_lock:
                pending_reels.append(new_reel)

                # Start the timer if not already running
                if not timer_running:
                    timer_running = True
                    threading.Timer(2.0, process_pending_reels).start()

            return jsonify({'status': 'pending reel/post'}), 200

        # Check if this is a message text for a pending reel
        if message_text:
            # Find the most recent pending reel for this sender (if any)
            current_pending_reel = None
            with pending_reels_lock:
                for reel in pending_reels:
                    if reel['sender_id'] == sender_id:
                        current_pending_reel = reel
                        break

            if current_pending_reel:
                # If there's a pending reel from this sender, update it with the message text
                # and remove it from the queue
                with pending_reels_lock:
                    pending_reels.remove(current_pending_reel)

                # Check if it's a user mention
                if message_text in DISCORD_USER_IDS:
                    send_message_to_discord(
                        username=current_pending_reel['username'],
                        message_text=message_text,
                        reel_url=current_pending_reel['url'],
                        media_type=current_pending_reel['media_type'],
                        sender_id=current_pending_reel['sender_id']
                    )
                    return jsonify({'status': 'sent to user'}), 200
                else:
                    # Regular message text with the reel
                    send_message_to_discord(
                        username=current_pending_reel['username'],
                        message_text=message_text,
                        reel_url=current_pending_reel['url'],
                        media_type=current_pending_reel['media_type'],
                        sender_id=current_pending_reel['sender_id']
                    )
                    return jsonify({'status': 'sent to server'}), 200
            else:
                # Just a regular text message without a reel
                send_message_to_discord(username, message_text, None, media_type="post", sender_id=sender_id)
                return jsonify({'status': 'success'}), 200

        # Handle regular messages
        send_message_to_discord(username, message_text, None, media_type="post", sender_id=sender_id)
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


def process_pending_reels():
    """Processes all pending reels/posts in the queue."""
    global timer_running

    with pending_reels_lock:
        # Reset the timer running flag
        timer_running = False

        # Process all pending reels
        while pending_reels:
            reel = pending_reels.popleft()

            # Send the reel to Discord
            send_message_to_discord(
                username=reel['username'],
                message_text=reel.get('message_text'),
                reel_url=reel['url'],
                media_type=reel.get('media_type', 'reel'),
                sender_id=reel['sender_id']
            )

            logger.info(f"Processed reel/post from {reel['username']}")

        logger.info("All pending reels/posts processed")


def send_message_to_discord(username, message_text, reel_url, media_type="reel", sender_id=None):
    """Sends a message to Discord with the Instagram username and message content."""
    global is_discord_client_running

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            # --- CASE 1: DM to a user by specifying their name ---
            first_word = message_text.split()[0] if message_text else ''
            if first_word in DISCORD_USER_IDS:
                user = await client.fetch_user(DISCORD_USER_IDS[first_word])
                if user:
                    # If message is just the name, don't send any message text
                    actual_message = None if message_text.strip() == first_word else ' '.join(message_text.split()[1:])
                    await send_reel_with_context(
                        user, username, actual_message, reel_url,
                        context_type="dm",
                        media_type=media_type,
                        sender_id=sender_id
                    )
                    logger.info(f"Sent DM to {first_word}")
                return

            # --- CASE 2: Server, reel only (no message) ---
            if reel_url and not message_text:
                channel = client.get_channel(DISCORD_CHANNEL_ID)
                if channel:
                    await send_reel_with_context(
                        channel, username, None, reel_url,
                        context_type="server_no_message",
                        media_type=media_type,
                        sender_id=sender_id
                    )
                    logger.info("Sent reel only to server")
                return

            # --- CASE 3: Server, reel with message ---
            if reel_url and message_text:
                channel = client.get_channel(DISCORD_CHANNEL_ID)
                if channel:
                    await send_reel_with_context(
                        channel, username, message_text, reel_url,
                        context_type="server_with_message",
                        media_type=media_type,
                        sender_id=sender_id
                    )
                    logger.info("Sent reel + message to server")
                return

            # --- REGULAR MESSAGE (no reel, just text) ---
            channel = client.get_channel(DISCORD_CHANNEL_ID)
            if channel:
                await send_reel_with_context(
                    channel, username, message_text, None,
                    context_type="server_text_only",
                    media_type=media_type,
                    sender_id=sender_id
                )
                logger.info("Sent regular message to server")
        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")
        finally:
            logger.info("Closing Discord client")
            await client.close()

    def run_discord_client():
        global is_discord_client_running

        # Wait until no other Discord client is running
        while True:
            with discord_client_lock:
                if not is_discord_client_running:
                    is_discord_client_running = True
                    break
            # Wait a short time before checking again
            time.sleep(0.1)

        try:
            client.run(DISCORD_BOT_TOKEN)
        except Exception as e:
            logger.error(f"Error running Discord client: {e}")
        finally:
            # Mark that this client is no longer running
            with discord_client_lock:
                is_discord_client_running = False

    try:
        threading.Thread(target=run_discord_client).start()
    except Exception as e:
        logger.error(f"Error starting Discord client thread: {e}")
        # Make sure to release the lock if we fail to start the thread
        with discord_client_lock:
            is_discord_client_running = False


async def send_reel_with_context(target, username, message_text, reel_url, context_type="server_with_message", media_type="reel", sender_id=None):
    """Send message (and optional reel/post) in a single message, with context_type for clarity."""
    message_parts = []

    # --- DM CASE ---
    if context_type == "dm":
        if username:
            if sender_id:
                message_parts.append(f"**From**: {username}{ZERO_WIDTH_MARKER + encode_invisible(sender_id)}")
            else:
                message_parts.append(f"**From**: {username}")
        if message_text:
            # Parse message for @mentions
            parsed_message = parse_mentions(message_text)
            message_parts.append(f"**Message**: {parsed_message}")

    # --- SERVER, REEL ONLY ---
    elif context_type == "server_no_message":
        if username:
            if sender_id:
                message_parts.append(f"**From**: {username}{ZERO_WIDTH_MARKER + encode_invisible(sender_id)}")
            else:
                message_parts.append(f"**From**: {username}")

    # --- SERVER, REEL WITH MESSAGE ---
    elif context_type == "server_with_message":
        if username:
            if sender_id:
                message_parts.append(f"**From**: {username}{ZERO_WIDTH_MARKER + encode_invisible(sender_id)}")
            else:
                message_parts.append(f"**From**: {username}")
        if message_text:
            # Parse message for @mentions
            parsed_message = parse_mentions(message_text)
            message_parts.append(f"**Message**: {parsed_message}")

    # --- SERVER, TEXT ONLY ---
    elif context_type == "server_text_only":
        if username:
            if sender_id:
                message_parts.append(f"**From**: {username}{ZERO_WIDTH_MARKER + encode_invisible(sender_id)}")
            else:
                message_parts.append(f"**From**: {username}")
        if message_text:
            # Parse message for @mentions
            parsed_message = parse_mentions(message_text)
            message_parts.append(f"**Message**: {parsed_message}")

    # Prefix every message with '> ' to make it a quote in Discord
    quoted_message = '> ' + '\n> '.join(message_parts) if message_parts else None

    # --- Send the reel/post if present ---
    if reel_url:
        file_path, file_size = download_reel(reel_url, media_type)
        # If download failed (post is private, deleted, etc)
        if file_size is None:
            return 0
        if file_path:
            try:
                await target.send(
                    content=quoted_message,
                    file=discord.File(file_path)
                )
                logger.info(f"Sent {media_type} as file ({file_size} bytes) with context [{context_type}]")
            except Exception as e:
                logger.error(f"Error sending file: {str(e)}")
                message_parts.append(f"File is bigger than 10MB, sending [__temporary link__]({reel_url}) instead")
                # Re-quote with new lines
                quoted_message = '> ' + '\n> '.join(message_parts)
                await target.send(quoted_message)
            finally:
                Path(file_path).unlink()
        else:
            message_parts.append(f"-# File is bigger than 10MB, sending [__temporary link__]({reel_url}) instead")
            quoted_message = '> ' + '\n> '.join(message_parts)
            await target.send(quoted_message)
            if file_size:
                logger.info(f"Sent {media_type} as link (original size: {file_size} bytes) [{context_type}]")
            else:
                logger.info(f"Sent {media_type} as link (download failed) [{context_type}]")
    else:
        # For regular messages without reel/post
        await target.send(quoted_message)
        logger.info(f"Sent regular message [{context_type}]")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
