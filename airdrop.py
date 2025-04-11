import requests

headers = {
    'Content-Type': 'application/json',
}

json_data = {
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'requestAirdrop',
    'params': [
        '3PmrYZ9KD3GLLnmGjJYcuGmt3zq2BBG34JLUhoUv7ZSL',
        1000000000,
    ],
}

response = requests.post('https://api.devnet.solana.com', headers=headers, json=json_data)
print(response.text)