from pyngrok import ngrok, conf

# 1. AUTHENTICATE
# This is the token you found yesterday
conf.get_default().auth_token = "39WWVXTGE6Fn123UzURLJsllJtr_7RmXzdhAq9mNx2KJ395"

# 2. START TUNNEL ON PORT 8000
# FastAPI runs on port 8000, so we open that port
public_url = ngrok.connect(8000).public_url

print("\n====================================================")
print("✅ NGROK IS RUNNING!")
print(f"🌍 YOUR PUBLIC URL: {public_url}")
print("👉 Copy this URL (without http://) for the next step.")
print("====================================================\n")

# Keep running
input("Press Enter to stop...")