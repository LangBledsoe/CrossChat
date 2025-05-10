[![Google Cloud Deployment](https://github.com/LangBledsoe/CrossChat/actions/workflows/cloud-deploy.yml/badge.svg)](https://github.com/LangBledsoe/CrossChat/actions/workflows/cloud-deploy.yml) [![Python Linting](https://github.com/LangBledsoe/CrossChat/actions/workflows/lint.yml/badge.svg)](https://github.com/LangBledsoe/CrossChat/actions/workflows/lint.yml)

# Project Overview

CrossChat is a bot that connects Instagram and Discord. Its main use is for sending posts, reels, and messages from Instagram to Discord. However, you can also reply to sent Instagram content directly from Discord.

![CrossChat Poster](/pictures/CrossChatPoster.png "CrossChat Poster")

# How to set up a custom instance

## Before you begin

Copy the content below and paste it into a secure text editor on your computer. As we go through the setup steps, you will be pasting secrets into this document as they get created. For the values with zeros, you will be replacing those values with secrets. For the empty quotes, you will be pasting secrets inside the empty quotes.

```
DISCORD_BOT_TOKEN = ""
DISCORD_CHANNEL_ID = 0
INSTAGRAM_BOT_USER_ID = 0
INSTAGRAM_ACCESS_TOKEN = ""
VERIFY_TOKEN = ""
DISCORD_USER_IDS = {
    "Bob": "",
    "John": "",
    "Tim": ""
}
DISCORD_PUBLIC_KEY = ""
DISCORD_APP_ID = 0
```

## Create the Discord Bot

1. Go to https://discord.com/developers and click “Get Started”.

![Image](/pictures/Discord/1.png "Image")

2. Click on “New Application” in the top right corner.

![Image](/pictures/Discord/2.png "Image")

3. Name your application.

![Image](/pictures/Discord/3.png "Image")

4. Copy your Application ID and Public Key and put them into the secrets file. Set DISCORD_APP_ID as the Application ID, and DISCORD_PUBLIC_KEY as the Public Key.

![Image](/pictures/Discord/4.png "Image")

5. Click on “Bot” in the left menu, then click “Reset token”. Copy the token value into your secrets file as DISCORD_BOT_TOKEN. 

![Image](/pictures/Discord/5.png "Image")

6. Scroll down and turn on “Message Content Intent”.

![Image](/pictures/Discord/messagecontent-CORRECT.png "Image")

7. Click on "OAth2" in the left menu.

![Image](/pictures/oath1.png "Image")

8. Scroll down to "OAuth2 URL Generator" and select "Bot".

![Image](/pictures/oath2.png "Image")

9. Scroll down to the bottom of the page, copy the generated URL, and paste it in your browser.

![Image](/pictures/oath3.png "Image")

10. This will open a prompt on Discord to add the bot to your server. Select the server you want to add it to.

![Image](/pictures/Discord/7.png "Image")

11. Click on the settings gear in the bottom left corner.

![Image](/pictures/Discord/8.png "Image")

12. Search “Advanced” and turn on developer mode.

![Image](/pictures/Discord/9.png "Image")

13. Right-click on each member in your server and copy their User ID into the secrets file. In DISCORD_USER_IDS, each member's first name should be on the left side, with their User ID on the right side.

![Image](/pictures/Discord/10.png "Image")

14. Right-click on the channel you want the bot to send to and copy the Channel ID. In your secrets file, paste that as the value for DISCORD_CHANNEL_ID.

![Image](/pictures/Discord/11.png "Image")

## Create a Facebook Developer Account

1. Create an Instagram account: https://www.instagram.com/. This will end up being the bot account you send stuff to.

2. Create or log in to an existing Facebook account: https://www.facebook.com/

3. While logged into your Facebook account, go to https://developers.facebook.com/.

4. Click on getting started in the top right corner.

![Image](/pictures/2.png "Image")

5. Go through the first three steps to create your Meta Developers account. You will be asked to verify your email and add a phone number.

![Image](/pictures/3.png "Image")

6. On the “About you section”, select “Developer”.

![Image](/pictures/4.png "Image")

7. Click on “Create App”.

![Image](/pictures/5.png "Image")

8. Fill out your name and email, then click "Next".

![Image](/pictures/6.png "Image")

9. Select "Other", then "Next".

![Image](/pictures/7.png "Image")

10. Select "Business", then "Next".

![Image](/pictures/8.png "Image")

11. Click "Create App".

![Image](/pictures/9.png "Image")

12. Click Set Up” on the Instagram box.

![Image](/pictures/10.png "Image")

13. Click on “App Roles” then “Roles”.

![Image](/pictures/14.png "Image")

14. Click on “Add people”.

![Image](/pictures/15.png "Image")

15. Click on “Instagram Test User” at the bottom and search for the Instagram account you made and click “Add”.

![Image](/pictures/16.png "Image")

16. Open a new tab and go to https://www.instagram.com/accounts/manage_access.

17. Click on “Tester Invites” and accept the pending invitation.

![Image](/pictures/24.png "Image")

18. Close that tab, and go back to your Facebook Developers page. Click on “Instagram”, then “API setup with Instagram login”, then "Add Account".

![Image](/pictures/18.png "Image")

19. Log in to the Instagram account you made.

![Image](/pictures/19.png "Image")

20. Upon log in, you will be prompted to change your account to a "Professional Account". Click "Change".

![Image](/pictures/20.png "Image")

21. Select "Business".

![Image](/pictures/21.png "Image")

22. Pick whatever category your heart desires, then on the next page click “Do not use my contact information”.

![Image](/pictures/22.png "Image")

23. Your business account has been made. Close the tab and go back to the Facebook developer portal you have open.

![Image](/pictures/23.png "Image")

24. You should now see a green check next to “Generate acces tokens”. Click on "Generate token", then copy the token into the secrets file. Set it as the value for INSTAGRAM_ACCESS_TOKEN. Next, click on the account ID of the Instagram account (under the username) to copy it to your clipboard. Set it as the value for INSTAGRAM_BOT_USER_ID in your secrets file. After that, turn on webhooks.

![Image](/pictures/25.png "Image")

25. In your secrets file, choose whatever you want for VERIFY_TOKEN. If you are uncreative you can use "i_love_crosschat".

## Configure the project on Google Cloud

1. Go to https://cloud.google.com and sign in with your Google account.

2. Once signed in, click on "Console" in the top right corner.

![Image](/pictures/26.png "Image")

3. Click on the projects menu on the top of the screen and select “New Project”.

![Image](/pictures/27.png "Image")

4. Name the project and create it.

![Image](/pictures/28.png "Image")

5. In your new project, click on the terminal button in the upper right corner.

![Image](/pictures/29.png "Image")

6. In the terminal, paste “git clone https://github.com/LangBledsoe/CrossChat.git” and click the enter key. Next, click on “Open Editor”.

![Image](/pictures/37.png "Image")

7. Drag the terminal up to make it easier to see. Then, in the editor, expand the “CrossChat” folder and click on mysecrets.json. In the text editor, paste the contents of the secret file you’ve been maintaining into mysecrets.json, so that it looks like the default version of the file but with all your custom secrets. After all the secrets are inputted, click on “Open Terminal”.

![Image](/pictures/38.png "Image")

8. Paste “cd CrossChat/ && bash setup.sh” into the terminal and click the enter key to execute the setup script. Upon successful finish, it will look like this:

![Image](/pictures/39.png "Image")

9. Go to https://console.cloud.google.com/run and click on "webhook-app".

![Image](/pictures/40.png "Image")

10. Copy the link at the top of the page.

![Image](/pictures/41.png "Image")

11. Go back to your Facebook Developer portal and go to the “API setup with Instagram login”. Paste the URL you copied in the “Callback URL” box and add “/webhook” to the end of the link. Paste in the value for VERIFY_TOKEN you chose. Then click “Verify” and “Save”, and subscribe to messages. After, switch your app to live by clicking the switch at the top of the page.

![Image](/pictures/42.png "Image")

12. Since you don't have a privacy policy, it will not let you make the app live. Click the “Basic Settings” hyperlink.

![Image](/pictures/43.png "Image")

## Create a Privacy Policy

1. In a new tab, go to https://www.freeprivacypolicy.com/

2. Click on “Free Privacy Policy Generator”.

![Image](/pictures/privacy_policy/priv1.png "Image")

3. Select “App”, then continue to “Step 2”.

![Image](/pictures/privacy_policy/priv2.png "Image")

4. Write in an app name, select “I’m an Individual”, then select “United States” as the country and “California” as the state. After that, click “Next Step”.

![Image](/pictures/privacy_policy/priv3.png "Image")

5. On the next screen, don’t check any of the boxes. Just click “Next step”.

![Image](/pictures/privacy_policy/priv5.png "Image")

6. Select “No, I don’t want a Professional Privacy Policy”, then click “Next Step”.

![Image](/pictures/privacy_policy/priv6.png "Image")

7. Enter an email, then click “Generate”.

![Image](/pictures/privacy_policy/priv7.png "Image")

8. Copy the link to your privacy policy.

![Image](/pictures/privacy_policy/priv8.png "Image")

9. Go back to the Facebook Developer portal and paste your privacy policy link into the box, click “Save changes”, then click the switch to turn the app live.

![Image](/pictures/44.png "Image")

10. Close all tabs related to the Facebook Developer portal. You will no longer need them.

## Configure the Discord bot to send messages to Instagram

1. Go back to https://console.cloud.google.com/run and click on "discord-handler".

![Image](/pictures/45.png "Image")

2. Copy the link at the top of the page.

![Image](/pictures/46.png "Image")

3. Go back to your Discord application at https://discord.com/developers, then go to “General Information” and paste your link in the “Interactions Endpoint URL” and then save.

![Image](/pictures/47.png "Image")

## Test the bot

1. Everything should be set up now. To test it, send a reel/post to your Instagram bot account.

2. Open your Discord server and check if the post/reel was sent to the channel. Because the bot is serverless, it needs to boot up every time it is used. It also needs to download the media, so the bot may take around 30 seconds to send the post/reel.

3. Once the bot has sent the post/reel, it'll look something like this:

![Image](/pictures/48.png "Image")

4. Next, let's verify that the bot can reply to messages. Right click on the message the bot just sent, then click on "Apps", then click on "Send Instagram DM".

![Image](/pictures/49.png "Image")

5. A prompt will appear. Type in a message and click "Send". Once you send the message, the bot will let you know it sent it:

![Image](/pictures/50.png "Image")

6. Open whatever Instagram account you sent the post/reel to your bot on and verify that you received the message:

![Image](/pictures/51.png "Image")

7. Congratulations 🎉 You have successfully set up a custom instance of CrossChat. Now give your friends the username of the Instagram bot and enjoy the experience!

# Logo

Here's the logo I use for my instance in case you want to use it for your bot:

![Image](/pictures/logo.png "Image")

