# Databricks Lakebase Ticketing System

A support ticketing system built as a Databricks App that:
- Connects to **Lakebase** (Databricks-managed Postgres) using a single `LAKEBASE_URL` secret
- Manages support tickets with message threads and status tracking
- Provides a Flask web UI for creating tickets, adding messages, and updating ticket status
- Uses proper database constraints (foreign keys, CHECK constraints) for data integrity
- Authenticates users via Databricks workspace headers

## Features

- **Ticket Management**: Create, view, and track support tickets
- **Message Threads**: Add messages to tickets for ongoing conversations
- **Status Tracking**: Update ticket status (open, in_progress, resolved, closed)
- **User Authentication**: Automatic user identification via Databricks workspace
- **Database Schema**: Proper foreign keys and CHECK constraints for data integrity

## Files

- `app.py` - Flask web app with ticket management endpoints
- `lakebase.py` - Lakebase connection helper and table creation functions
- `templates/tickets.html` - Web UI for ticket listing, creation, and messaging
- `setup_secrets.py` - One-time script to store the Lakebase connection URL in secrets
- `app.yaml` - Databricks App deployment config
- `.env.example` - Local dev env var template (copy to `.env`, do not commit real values)

## Database Schema

### tickets table
```sql
CREATE TABLE tickets (
    ticket_id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### ticket_messages table
```sql
CREATE TABLE ticket_messages (
    message_id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id) ON DELETE RESTRICT,
    message_text TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Step-by-step setup

### 1. Create a Lakebase instance and a native-password role

1. In your Databricks workspace, go to **Catalog** (left sidebar) and select the **Lakebase** tab (or search "Lakebase" in the workspace search bar).
2. Click **Create Lakebase instance** (sometimes labeled **Create database instance**).
   - Give it a name (e.g. `ticketing-system-db`).
   - Choose the capacity/compute size and region appropriate for your workload (defaults are fine to start).
   - Click **Create** and wait for the instance to reach the **Available**/**Running** state.
3. Open the newly created instance, then go to the **Roles & Databases** tab (sometimes called **Permissions** or **Roles**).
4. **Enable native (password) authentication** for the instance if it isn't already on:
   - Look for an authentication setting such as **Native passwords** or **Password authentication** and toggle/enable it. By default some Lakebase instances only support OAuth/token-based auth — you need password auth enabled so the role below gets a static password instead of a short-lived token.
5. **Create a new role**:
   - Click **Add role** / **Create role**.
   - Choose **Password** as the authentication method (not OAuth).
   - Name the role (e.g. `ticketing_app`) and let Databricks generate (or set) a password.
6. **Copy the connection URL** shown for the role. It will look like:

   ```
   postgresql://<role>:<password>@<host>.database.cloud.databricks.com:5432/databricks_postgres?sslmode=require
   ```

   Keep this URL — you'll paste it into `setup_secrets.py`'s prompt in the next step.

### 2. Store your secrets

Run once from a **Databricks notebook** in your workspace (no CLI needed):

1. Create a new notebook (or open the Git folder you'll create in step 4, once it's cloned) and attach it to any running cluster.
2. In a cell, run:

   ```python
   %sh python setup_secrets.py
   ```

   or open a terminal from the notebook (**Run** > **Open terminal**, if enabled on your cluster) and run `python setup_secrets.py` there.

This prompts (via `getpass`, so nothing is echoed or written to disk/shell history) for:
- Your **Lakebase connection URL** (from step 1) → stored as secret `database/lakebase-url`

### 3. Configure environment variables (local dev)

Copy `.env.example` to `.env` and paste your Lakebase URL as `LAKEBASE_URL` for local runs:

```bash
cp .env.example .env
```

For deployment, `app.yaml` already pulls `LAKEBASE_URL` from the `database/lakebase-url` secret automatically — no manual editing needed there.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run locally

```bash
python app.py
```

Open http://localhost:8000 in your browser to access the ticketing system.

### 6. Create a Git folder in Databricks and deploy the app (no CLI required)

All of this is done through the Databricks workspace UI:

1. **Create a Git folder**:
   - In the Databricks workspace sidebar, click **Workspace** > **Create** > **Git folder** (in older UIs this is called **Repos** > **Add Repo**).
   - Paste the Git URL of this project's repository (e.g. your GitHub/GitLab remote for this codebase).
   - Choose a folder name and click **Create Git folder**. Databricks will clone the repo directly into your workspace — this becomes the source for your app.

2. **Create the Databricks App**:
   - In the sidebar, go to **Compute** > **Apps** (or search "Apps" in the workspace search bar).
   - Click **Create app**, then choose **Custom** (or "From scratch").
   - Give the app a name (e.g. `ticketing-system`).

3. **Point the app at your Git folder**:
   - When prompted for the source code location, select **Workspace files** / **Git folder** and browse to the Git folder you created in step 1 (the folder containing `app.py` and `app.yaml`).
   - Databricks will read `app.yaml` from that folder automatically to configure the `command` and `env` (including the `LAKEBASE_URL`, `MASSIVE_API_BASE_URL`, and secret scope/key references).

4. **Deploy**:
   - Click **Deploy** (or **Create and deploy**) in the Apps UI. Databricks will build and start the app using the Git folder's current contents — no `databricks` CLI commands are needed.
   - Whenever you update the code, pull the latest changes into the Git folder (**Git folder** > **Pull**, via the UI) and click **Deploy** again in the Apps UI to redeploy.

5. Once deployed, open the app's URL from the Apps UI to access the ticketing system. You should be able to:
   - View all tickets
   - Create new tickets
   - Add messages to tickets
   - Update ticket status
   - See your username automatically populated (from Databricks workspace)

## API Endpoints

- `GET /` - Main UI: List all tickets with title, status, creator, and creation time
- `GET /healthz` - Health check endpoint
- `POST /tickets` - Create a new ticket (JSON body: `{"title": "...", "message": "..."}`, auto-populates created_by from user)
- `GET /tickets/<ticket_id>` - View ticket detail with all messages
- `POST /tickets/<ticket_id>/messages` - Add a message to a ticket (JSON body: `{"message": "..."}`, auto-populates author from user)
- `PATCH /tickets/<ticket_id>` - Update ticket status (JSON body: `{"status": "open|in_progress|resolved|closed"}`)

## Usage Example

### Creating a ticket
```bash
curl -X POST http://your-app-url/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "Login issues", "message": "Users cannot log in to the portal"}'
```

### Adding a message to a ticket
```bash
curl -X POST http://your-app-url/tickets/1/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Investigating the database connection"}'
```

### Updating ticket status
```bash
curl -X PATCH http://your-app-url/tickets/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'
```

## Technical Notes

- **Authentication**: Users are identified via the `X-Forwarded-Email` header (automatically provided by Databricks Apps)
- **Database Connection**: Uses a single `LAKEBASE_URL` secret pointing at a native Postgres role with a static password — no token refresh logic needed
- **Data Integrity**: Foreign key constraint with `ON DELETE RESTRICT` prevents ticket deletion if messages exist; CHECK constraint ensures only valid status values
- **Tables**: Created automatically on first app startup via `ensure_tickets_table()` and `ensure_ticket_messages_table()` in `lakebase.py`

## Future Enhancements

- Add ticket assignment to specific users
- Email notifications on status changes or new messages
- Search and filter capabilities
- Rich text editor for messages
- File attachments on tickets
- Ticket priority levels
- SLA tracking and escalation
