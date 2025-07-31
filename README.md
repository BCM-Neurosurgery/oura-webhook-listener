# Oura Sync Project

This project is part of a larger pipeline to manage multi-modal data collection for clinical research. This repo is a lightweight system to listen to posts from a webhook. It will ideally listen to posts from the [Oura Ring]([https://cloud.ouraring.com/docs/]) API and save the details of the post. It will also save the post timestamp for a checker (integrated into another system) to see that there is new data available. The ultimate goal is to deploy this to an EC2 server and integrate it into a shared data infrastructure.

## Project Structure

```bash
oura_webhook_listener/
├── config.json                # API keys, server URLs, folder paths
├── run_webhook.py             # Starts the Flask webhook server
├── register_webhook.py        # Registers webhook subscriptions with Oura API
├── requirements.txt           # (Optional) pip-based dependencies
├── README.md                  # Project overview and instructions
│
├── logs/                      # (Optional) log files for server or cron jobs
│
├── oura_data/                 # Auto-created at runtime
│   ├── oura_tokens.json       # Stores OAuth2 tokens per participant
│   ├── participant_map.json   # Maps Oura user IDs to participant IDs
│   ├── upload_state.json      # Tracks processed webhook files
│   └── webhook_posts/         # Stores full webhook payloads by user/modality
│       └── <user>/
│           └── <modality>/
│               └── <timestamp>.json
│
├── routes/                    # Flask route definitions
├── services/                  # OAuth2 and Oura API helper modules
└── utils/                     # Helper utilities (e.g., token refresh scripts)    
```

## Project Requirements
This project is built for Python 3.10** using Conda. You can install dependencies through Conda or pip.

### Conda Installation
```bash
conda env create -f environment.yml
conda activate oura_env
```
### Pip Installation
```bash
pip install -r requirements.txt
```

## Testing Webhook Listener
From the project folder, run:
```bash
python run_webhook.py
```

You'll see something like this (if it was successful):
```bash
Running on <LOCAL_SERVER>
```

In second terminal, send a curl post to test the Flask listener (see curl_commands.txt for an idea of what to send):
```bash
curl -X POST <LOCAL_SERVER>/v2/webhook/subscription \
     -H "Content-Type: application/json" \
     -d '{
           "event": "sleep",
           "summary_date": "2025-05-08",
           "source": "simulated_test"
         }'
```

You should be able to see posts in both oura_data/webhook_comms/ -> should be the event and timestamp and oura_data/webhook_posts/ -> should be the message you sent with curl. These file names should be the same timestamp. 
