# Google Classroom Setup Guide

To connect to your Google Classroom, you need to set up a Google Cloud Project and enable the Classroom API. Follow these steps:

## Prerequisites

1.  **Google Account**: Ensure you have a Google account with access to Google Classroom.
2.  **Google Cloud Console**: Go to [https://console.cloud.google.com/](https://console.cloud.google.com/).

## Step 1: Create a Project

1.  In the Google Cloud Console, click on the project dropdown at the top.
2.  Click **New Project**.
3.  Enter a project name (e.g., "Classroom Integration") and click **Create**.
4.  Select the newly created project.

## Step 2: Enable the Classroom API

1.  In the left sidebar, go to **APIs & Services** > **Library**.
2.  Search for "Google Classroom API".
3.  Click on **Google Classroom API** and then click **Enable**.

## Step 3: Configure OAuth Consent Screen

1.  Go to **APIs & Services** > **OAuth consent screen**.
2.  Select **External** (unless you are a G Suite user and want to limit to your organization, then select Internal if possible, but External is generally easier for personal testing).
3.  Click **Create**.
4.  Fill in the **App Information**:
    *   **App name**: Classroom Reader
    *   **User support email**: Your email address
    *   **Developer contact information**: Your email address
5.  Click **Save and Continue**.
6.  **Scopes**: Click **Add or Remove Scopes**.
    *   Search for `classroom.courses.readonly` and `classroom.coursework.me.readonly`.
    *   Select them and click **Update**.
    *   Or simply manually add: `https://www.googleapis.com/auth/classroom.courses.readonly`
7.  Click **Save and Continue**.
8.  **Test Users**: Add your own email address as a test user.
9.  Click **Save and Continue**.

## Step 4: Create Credentials

1.  Go to **APIs & Services** > **Credentials**.
2.  Click **Create Credentials** > **OAuth client ID**.
3.  **Application type**: Select **Desktop app**.
4.  **Name**: Enter a name (e.g., "Desktop Client").
5.  Click **Create**.
6.  A pop-up will appear with your Client ID and Client Secret.
7.  Click **Download JSON**.
8.  **Rename the downloaded file to `credentials.json`** and place it in the root directory of this project (`c:\Users\Ran Oren\study_together\`).

## Running the Script

Once you have placed `credentials.json` in the folder, you can run the script (which I will create next) to connect and read your course data.
