# Getting Google credentials for gtask

Google Tasks holds private data, so gtask cannot use a plain API key. It uses
OAuth 2.0: you register a tiny "app" with Google once, and then log in through
your browser. This takes about ten minutes and costs nothing. Every person who
runs gtask does this once with their own Google account.

## 1. Open Google Cloud console and create a project

1. Go to <https://console.cloud.google.com/> and sign in with the Google
   account whose tasks you want to manage. Accept the terms if asked.
2. At the top of the page click the project selector (it says
   **Select a project** or shows a project name) → **New project**.
3. Name it `gtask`, leave the rest as is, click **Create**.
4. Wait for the notification, then make sure `gtask` is the selected project
   (the selector at the top should show it).

## 2. Enable the Google Tasks API

1. Open <https://console.cloud.google.com/apis/library/tasks.googleapis.com>
   (or: ☰ menu → **APIs & Services** → **Library** → search "Google Tasks API").
2. Click **Enable**.

## 3. Set up the consent screen (Google Auth Platform)

1. ☰ menu → **APIs & Services** → **OAuth consent screen**. This opens the
   **Google Auth Platform** page.
2. If it says the platform is not configured yet, click **Get started**.
   You get a short wizard:
   - **App information**: App name `gtask`, User support email: your email.
   - **Audience**: **External**. (Internal only exists for Google Workspace
     organisations; a normal Gmail account cannot pick it.)
   - **Contact information**: your email.
   - **Finish**: tick the policy agreement, click **Create**.

## 4. Allow your account to log in

A new External app starts in **Testing** status, which means only accounts on
its test-user list may log in.

1. In the Google Auth Platform left menu click **Audience**.
2. Under **Test users** click **Add users**, enter your Gmail address, **Save**.

**About the 7-day limit.** While the app stays in Testing, Google throws away
the login after 7 days and gtask will say "token expired, run gtask login".
To stop that, on the same **Audience** page click **Publish app** and confirm.
You do **not** need to submit the app for verification; ignore that part. The
only consequence is that the login page shows "Google hasn't verified this
app". Click **Advanced** → **Go to gtask (unsafe)**. That warning is expected
for a personal app that only you use.

## 5. Create the OAuth client

1. In the Google Auth Platform left menu click **Clients** → **Create client**.
2. Application type: **Desktop app**. Name: `gtask cli`. Click **Create**.
3. In the dialog click **Download JSON**. You get a file named like
   `client_secret_1234567890-abc.apps.googleusercontent.com.json`, usually in
   `~/Downloads`. Close the dialog. (You can download it again later from the
   Clients page with the download icon.)

Google's own documentation says the "secret" in a Desktop app client is not
actually confidential, because it ships inside apps. gtask still stores it
with owner-only permissions.

## 6. Connect gtask

```bash
gtask login --credentials ~/Downloads/client_secret_*.json
```

- A browser tab opens. Pick the same Google account.
- If you see "Google hasn't verified this app": **Advanced** →
  **Go to gtask (unsafe)**.
- Tick / allow "Create, edit, organize, and delete all your tasks" → **Continue**.
- The tab says "The authentication flow has completed. You may close this window."

Then check:

```bash
gtask lists
gtask ls
```

gtask copied the client file to its config directory (`gtask status` shows
where), so future logins are just `gtask login`.

## What is stored where

| File | Purpose | Share it? |
|------|---------|-----------|
| `~/.config/gtask/client_secret.json` | Identifies the gtask app to Google | Harmless, but each person should make their own |
| `~/.config/gtask/token.json` | Your personal access; anyone holding it can read and change your tasks | **Never** |
| `~/.config/gtask/config.toml` | Default list | Harmless |

`gtask logout` deletes the token. To revoke access on Google's side, visit
<https://myaccount.google.com/permissions> and remove `gtask`.

## Sharing gtask with someone else

Each person repeats steps 1 to 6 with their own Google account and project.
(Alternatively you can add them under **Test users** in your project and give
them your `client_secret.json`, but then their access depends on your project,
so the recommended way is their own.)

## Troubleshooting

- **"Access blocked: gtask has not completed the Google verification process"**
  or **"Error 403: access_denied"**: your account is not on the Test users list
  (step 4) and the app is not published.
- **Asked to log in again every week / "invalid_grant"**: the app is still in
  Testing; publish it (step 4).
- **"Google Tasks API has not been used in project … or it is disabled"**:
  step 2 was skipped, or you enabled it in a different project.
- **"redirect_uri_mismatch"**: the client is not of type Desktop app. Create a
  new one (step 5).
- **"… is not a valid OAuth client file"**: you passed a different JSON (for
  example a service-account key). Download the client from the **Clients**
  page.
- **No browser opens**: gtask prints the URL; open it in a browser on the same
  machine. Logging in from a remote/SSH session is not supported.
