# Voting Web UI

The experimental app to collect votes via Power Automate requesting webhook on Microsoft Form submissions. For specific students organisations.

Limitations due to Power Automate:
- Webhook requests may fail without retrys
- Webhook requests does not contain the names of form question fields, needs to manually config the map between the names and IDs

## How to run?

1. Install the dependencies with `pip install -r requirements.txt`
2. Put `config.json` and `secrets.json` in `/instance`
3. Initialise the database with `python -m flask init-db`
4. Run the app with `python -m flask run`

   Set environment variable `OAUTHLIB_RELAX_TOKEN_SCOPE=1` and run `python -m flask run`

   If on HTTP, also set `OAUTHLIB_INSECURE_TRANSPORT=1`, optionally set `FLASK_ENV=development` for debug mode

   - In PowerShell: `$env:OAUTHLIB_RELAX_TOKEN_SCOPE=1`
   - On Linux: `OAUTHLIB_RELAX_TOKEN_SCOPE=1 python -m flask run`
5. Set up Microsoft Forms with one only free-text question being the voter ID (for public forms, private forms will use username part of logged in email as voter ID (assuming only one "@" in those email addresses)), other questions can be rankings or choices.
6. In Power Automate (only supported on Work or School account), create a flow that triggers on new form responses, and get the response details, then send a POST request to `/api/ballot-form` with the body of `String(form_body)`, and the headers containing `X-API-Key` with the value in `secrets.json`
