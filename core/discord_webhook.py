import requests
import json
import sys

def send_discord_message(webhook_url, content):
    """
    Sends a message to a Discord channel via Webhook.
    
    Args:
        webhook_url (str): The Discord Webhook URL.
        content (str): The message content to send.
    """
    if not webhook_url:
        print("Error: Webhook URL is empty.")
        return

    data = {
        "content": content
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(webhook_url, json=data, headers=headers)
        response.raise_for_status()
        print("Message sent successfully to Discord!")
    except requests.exceptions.HTTPError as err:
        print(f"Failed to send message: {err}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("Discord Webhook Sender")
    print("----------------------")
    
    # Simple CLI usage
    if len(sys.argv) == 3:
        url = sys.argv[1]
        msg = sys.argv[2]
        send_discord_message(url, msg)
    else:
        url = input("Enter your Discord Webhook URL: ").strip()
        msg = input("Enter message to send: ").strip()
        send_discord_message(url, msg)
