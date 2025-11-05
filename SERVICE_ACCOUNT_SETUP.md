# Google Service Account Setup for Headless Environments

This guide walks you through setting up a Google Service Account for the school lunch menu sync script. Service accounts allow the script to run completely unattended without requiring browser-based OAuth authentication.

## Why Use a Service Account?

- **No user interaction required** - Perfect for headless servers, cron jobs, and automation
- **No browser needed** - Works on servers without GUI
- **No token expiration issues** - Service accounts don't require refresh tokens
- **Simpler deployment** - Just copy one JSON file to your server

## Prerequisites

- A Google Cloud Platform account (free tier is sufficient)
- Access to the Google Calendar you want to sync to
- Administrative access to create service accounts in your GCP project

---

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name it something like "School Lunch Menu Sync"
4. Click **Create**
5. Wait for the project to be created, then select it

---

## Step 2: Enable the Google Calendar API

1. In your project, go to **APIs & Services** → **Library**
2. Search for "Google Calendar API"
3. Click on **Google Calendar API**
4. Click **Enable**
5. Wait for the API to be enabled (takes a few seconds)

---

## Step 3: Create a Service Account

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **Service Account**
3. Fill in the details:
   - **Service account name**: `lunch-menu-sync` (or any name you prefer)
   - **Service account ID**: Will auto-populate, you can leave it
   - **Description**: "Service account for syncing school lunch menus to Google Calendar"
4. Click **Create and Continue**
5. Skip the "Grant this service account access to project" step (click **Continue**)
6. Skip the "Grant users access to this service account" step (click **Done**)

---

## Step 4: Create and Download the Service Account Key

1. On the **Credentials** page, find your newly created service account under **Service Accounts**
2. Click on the service account email (looks like `lunch-menu-sync@your-project.iam.gserviceaccount.com`)
3. Go to the **Keys** tab
4. Click **Add Key** → **Create new key**
5. Select **JSON** as the key type
6. Click **Create**
7. A JSON file will be downloaded to your computer (e.g., `your-project-abc123.json`)
8. **⚠️ IMPORTANT**: Keep this file secure! It contains credentials that allow access to your calendar

---

## Step 5: Share Your Google Calendar with the Service Account

This is the critical step that many people forget!

1. Open [Google Calendar](https://calendar.google.com/)
2. Find the calendar you want to sync to (or create a new one)
3. Click the **⋮** (three dots) next to the calendar name
4. Select **Settings and sharing**
5. Scroll down to **Share with specific people**
6. Click **+ Add people**
7. Enter the service account email address:
   - This is in the JSON file you downloaded, under the `"client_email"` field
   - It looks like: `lunch-menu-sync@your-project.iam.gserviceaccount.com`
8. Set the permission to **Make changes to events** (or higher)
9. Click **Send**
10. You should NOT receive a notification email (service accounts don't have inboxes)

---

## Step 6: Get Your Calendar ID

You'll need your calendar ID to run the script:

1. In Google Calendar, go to **Settings and sharing** for your calendar
2. Scroll down to **Integrate calendar**
3. Copy the **Calendar ID**
   - For your primary calendar, it's usually your email address
   - For a custom calendar, it looks like: `abc123xyz@group.calendar.google.com`

---

## Step 7: Upload the Service Account Key to Your Server

Copy the JSON key file to your server:

```bash
# From your local machine
scp your-project-abc123.json user@your-server:~/school-lunch-google-calendar-sync/service-account.json

# Or using any other file transfer method (FTP, rsync, etc.)
```

**Security Best Practices**:
```bash
# Restrict file permissions so only you can read it
chmod 600 ~/school-lunch-google-calendar-sync/service-account.json

# Ensure it's owned by your user
chown $USER:$USER ~/school-lunch-google-calendar-sync/service-account.json
```

---

## Step 8: Update Your Sync Script

Update your shell scripts (`run_elementary_sync.sh`, `run_highschool_sync.sh`, etc.) to use the service account:

### Before:
```bash
python3 school_lunch_menu_google_calendar_sync.py \
  -u "https://..." \
  -c "your-calendar-id@group.calendar.google.com" \
  -p "FR: " \
  ...
```

### After:
```bash
python3 school_lunch_menu_google_calendar_sync.py \
  --service-account-file service-account.json \
  -u "https://..." \
  -c "your-calendar-id@group.calendar.google.com" \
  -p "FR: " \
  ...
```

**That's it!** You no longer need `credentials.json` or `token.json` when using a service account.

---

## Complete Example

Here's a complete example for NutriSlice:

```bash
#!/bin/bash

python3 school_lunch_menu_google_calendar_sync.py \
  --service-account-file ~/school-lunch-google-calendar-sync/service-account.json \
  -u "https://justadashcatering.api.nutrislice.com/menu/api/weeks/school/lagrange-sd-102/menu-type/park-junior-high" \
  -c "family14451540610974778791@group.calendar.google.com" \
  -p "FR: " \
  -o "grape" \
  -l INFO \
  -d ./logs \
  -w 52 \
  --replace-wg
```

And for FDMealPlanner:

```bash
#!/bin/bash

python3 school_lunch_menu_google_calendar_sync.py \
  --service-account-file ~/school-lunch-google-calendar-sync/service-account.json \
  -u "https://apiservicelocatorstenantquest.fdmealplanner.com/api/v1/data-locator-webapi/4/meals" \
  -c "your-calendar-id@group.calendar.google.com" \
  -p "HS: " \
  -o "blueberry" \
  -l INFO \
  -d ./logs \
  -w 52 \
  -a "123" \
  -i "456" \
  -m "789" \
  -e "1"
```

---

## Troubleshooting

### Error: "Service account file not found"
- Check the path to your JSON file
- Make sure you're running the script from the correct directory
- Use an absolute path: `--service-account-file /full/path/to/service-account.json`

### Error: "Failed to load service account credentials"
- Verify the JSON file is valid (open it in a text editor)
- Make sure you downloaded the JSON format (not P12)
- Try downloading a new key from the Google Cloud Console

### Error: "Access denied" or "Insufficient permissions"
- Make sure you shared the calendar with the service account email
- Verify the service account has "Make changes to events" permission or higher
- Double-check the calendar ID is correct

### Events aren't appearing in the calendar
- Verify you're looking at the correct calendar
- Check that the calendar ID matches what you're using in the script
- Run with `-l DEBUG` to see detailed logging

### "Google Calendar API has not been used in project..."
- Go back to Step 2 and enable the Google Calendar API
- Wait a few minutes for the API to fully activate
- Try running the script again

---

## Security Considerations

### Protecting Your Service Account Key

The service account JSON file is **sensitive** and should be treated like a password:

1. **Never commit it to version control**:
   ```bash
   # Add to .gitignore
   echo "service-account.json" >> .gitignore
   echo "*.json" >> .gitignore  # Or be more specific
   ```

2. **Restrict file permissions**:
   ```bash
   chmod 600 service-account.json
   ```

3. **Limit the service account's access**:
   - Only share the specific calendar(s) needed
   - Don't share your entire Google account or all calendars

4. **Rotate keys periodically**:
   - Delete old keys from the Google Cloud Console
   - Create new keys every 6-12 months

### If Your Key is Compromised

If you accidentally expose your service account key:

1. Go to **Google Cloud Console** → **IAM & Admin** → **Service Accounts**
2. Click on your service account
3. Go to the **Keys** tab
4. Click **⋮** next to the compromised key → **Delete**
5. Create a new key and update your server

---

## Converting from OAuth to Service Account

If you're currently using OAuth (`credentials.json` and `token.json`):

1. Follow the steps above to create a service account
2. Update your scripts to use `--service-account-file`
3. You can delete `credentials.json` and `token.json` (optional, but they're no longer needed)
4. The calendar permissions remain the same - events created via OAuth will still be accessible

---

## FAQ

### Q: Can I use the same service account for multiple calendars?
**A:** Yes! Just share each calendar with the service account email, and run separate sync commands with different calendar IDs.

### Q: Do I need to renew or refresh service account credentials?
**A:** No, service account credentials don't expire like OAuth tokens. They work until you delete them.

### Q: Can I use both OAuth and service account?
**A:** Yes, but not at the same time. Use `--service-account-file` for service account mode, or omit it for OAuth mode.

### Q: What if I want to use this on multiple servers?
**A:** Copy the same `service-account.json` file to each server. You can use the same service account on unlimited servers.

### Q: Is the free tier of Google Cloud sufficient?
**A:** Yes! Service accounts and the Google Calendar API are free. You only pay if you exceed very high usage limits (which you won't with this script).

---

## Additional Resources

- [Google Service Accounts Documentation](https://cloud.google.com/iam/docs/service-accounts)
- [Google Calendar API Documentation](https://developers.google.com/calendar/api/guides/overview)
- [Google Cloud Console](https://console.cloud.google.com/)

---

**Need Help?**

If you encounter issues not covered in this guide, please check:
1. The script logs (use `-l DEBUG` for detailed output)
2. The Google Cloud Console audit logs
3. Your calendar sharing settings

Happy syncing! 🍎📅


