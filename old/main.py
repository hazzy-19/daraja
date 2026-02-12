from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()


@app.post("/callback")
async def mpesa_callback(request: Request):
    # 1. GET DATA
    payload = await request.json()
    print("\n!!!! RECEIPT RECEIVED !!!!")

    # 2. CHECK SUCCESS
    result_code = payload['Body']['stkCallback']['ResultCode']
    if result_code != 0:
        error = payload['Body']['stkCallback']['ResultDesc']
        print(f"❌ Failed: {error}")
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # 3. EXTRACT DETAILS
    metadata = payload['Body']['stkCallback']['CallbackMetadata']['Item']
    amount = next(item['Value'] for item in metadata if item['Name'] == 'Amount')
    receipt = next(item['Value'] for item in metadata if item['Name'] == 'MpesaReceiptNumber')
    phone = next(item['Value'] for item in metadata if item['Name'] == 'PhoneNumber')

    print(f"✅ Success!")
    print(f"💰 Amount: {amount} KES")
    print(f"🧾 Receipt: {receipt}")
    print(f"📱 Phone: {phone}")

    return {"ResultCode": 0, "ResultDesc": "Accepted"}


if __name__ == "__main__":
    # Run the server on Port 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)