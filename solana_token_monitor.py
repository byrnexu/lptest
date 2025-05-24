import requests
import time
from collections import defaultdict
import json

# 配置
RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
CHECK_INTERVAL = 10  # 秒
TOP_N = 10  # 显示前N个最活跃的代币

# 存储交易计数
token_counter = defaultdict(int)

# 一些主要的 Solana 代币程序地址
TOKEN_PROGRAMS = [
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Token Program
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",  # Associated Token Program
]

def process_instruction(instruction):
    try:
        if 'parsed' not in instruction:
            return None
        
        parsed = instruction['parsed']
        if parsed['type'] == 'transferChecked':
            return parsed['info']['mint']
        elif parsed['type'] == 'transfer':
            return parsed['info']['mint']
        elif parsed['type'] == 'mintTo':
            return parsed['info']['mint']
        elif parsed['type'] == 'burn':
            return parsed['info']['mint']
    except Exception as e:
        print(f"Error processing instruction: {e}")
    return None

def get_token_transactions():
    try:
        for program_id in TOKEN_PROGRAMS:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    program_id,
                    {
                        "limit": 100
                    }
                ]
            }
            response = requests.post(RPC_ENDPOINT, json=payload)
            response_data = response.json()

            if 'error' in response_data:
                print(f"RPC Error for program {program_id}: {response_data['error']}")
                continue

            if 'result' not in response_data:
                print(f"Unexpected response format for program {program_id}")
                continue

            # 获取每个交易的详细信息
            for tx_info in response_data['result']:
                tx_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [
                        tx_info['signature'],
                        {
                            "maxSupportedTransactionVersion": 0,
                            "encoding": "jsonParsed"
                        }
                    ]
                }
                tx_response = requests.post(RPC_ENDPOINT, json=tx_payload)
                tx_data = tx_response.json()

                if 'result' in tx_data and tx_data['result']:
                    # 处理交易中的指令
                    for instruction in tx_data['result']['transaction']['message']['instructions']:
                        mint_address = process_instruction(instruction)
                        if mint_address:
                            token_counter[mint_address] += 1

                    # 处理交易中的元数据
                    if 'meta' in tx_data['result'] and 'postTokenBalances' in tx_data['result']['meta']:
                        for balance in tx_data['result']['meta']['postTokenBalances']:
                            if 'mint' in balance:
                                token_counter[balance['mint']] += 1

    except Exception as e:
        print(f"Error processing transactions: {e}")

def monitor_active_tokens():
    print("Starting Solana token activity monitor...")
    print("Monitoring token programs:", TOKEN_PROGRAMS)

    while True:
        try:
            get_token_transactions()

            # 显示最活跃的代币
            sorted_tokens = sorted(token_counter.items(), key=lambda x: x[1], reverse=True)[:TOP_N]
            print("\nTop Active Tokens:")
            for i, (token, count) in enumerate(sorted_tokens, 1):
                print(f"{i}. Token: {token} - Transactions: {count}")

        except requests.exceptions.RequestException as e:
            print(f"Network Error: {e}")
        except Exception as e:
            print(f"Unexpected Error: {e}")
            print(f"Error type: {type(e)}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor_active_tokens()
