## Quick Start

### Prerequisites

- Python 3.12 or higher
- Docker and Docker Compose
- Git
- A code editor (VS Code or Cursor)
- Discord bot token

### Quick Start

#### 1. Clone the repository

```bash
git clone https://github.com/datalumina/genai-launchpad.git
cd genai-launchpad
```

#### 2. Set up environment files

```bash
cp app/.env.example app/.env
cp docker/.env.example docker/.env
```

You can leave the `docker/.env` file as is for the quick start. However, you need to add your OpenAI API key to the `app/.env` file. Open `app/.env` and locate the `OPENAI_API_KEY` variable. Replace its value with your actual OpenAI API key:

```yaml
OPENAI_API_KEY=your_openai_api_key_here
```

You also need to create a discord bot and update the relevnt discord variables in the `app/.env` file.

#### 3. Build and start the Docker containers

```bash
cd ./docker
./start.sh
```

To run .sh scripts on Windows, install [Git Bash](https://git-scm.com/downloads/win), then right-click in the script’s folder and select “Git Bash Here.” Use ./scriptname.sh in the Git Bash terminal to execute the script.

#### 4. Make database migrations

```bash
cd ../app
./makemigration.sh  # Create a new migration
./migrate.sh        # Apply migrations
```

When prompted for a migration message, you can enter a brief description like "Initial migration" or "Launch".

#### 5. Start logging:

```bash
cd ../docker
./logs.sh
```

#### 6. Create virtual environment and install requirements

```bash
# Create a new virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS and Linux:
source venv/bin/activate

# Install the required packages
cd app
pip install -r requirements.txt
```

#### 7. Populate the vector store

To initialize the vector store with sample data, run:

```bash
python app/utils/insert_vectors.py
```

#### 8. Send event

Run the following command to send a test event using the invoice.json file and the request library:

```bash
python requests/send_event.py
```

You should get a `202` status code back and see the response logged in the terminal where you are running `./logs.sh`. Here you should see that the invoice service should be called and that the task is successfully completed.

This step creates necessary tables, indexes, and inserts initial vector data into the database.

#### 9. Check database

Connect to the database using your favorite database explorer (I use TablePlus). The default settings are:

- Host: localhost
- Port: 5432
- Database: psyche-voyage_database
- Username: psyche-voyage
- Password: super-secret-postgres-password

In the `events` table, you should see the event you just processed. It contains the raw data (JSON) in the `data` column and the processed event (JSON) with in the `task_context` column.

