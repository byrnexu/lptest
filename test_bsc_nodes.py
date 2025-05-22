import requests
import time
from concurrent.futures import ThreadPoolExecutor
import json

# BSC节点列表
NODES = {
    # 官方节点
    "BSC官方1": "https://bsc-dataseed.binance.org/",
    "BSC官方2": "https://bsc-dataseed1.defibit.io/",
    "BSC官方3": "https://bsc-dataseed1.ninicoin.io/",
    "BSC官方4": "https://bsc-dataseed2.defibit.io/",
    "BSC官方5": "https://bsc-dataseed3.defibit.io/",
    "BSC官方6": "https://bsc-dataseed4.defibit.io/",
    "BSC官方7": "https://bsc-dataseed2.ninicoin.io/",
    "BSC官方8": "https://bsc-dataseed3.ninicoin.io/",
    "BSC官方9": "https://bsc-dataseed4.ninicoin.io/",
    "BSC官方10": "https://bsc-dataseed1.binance.org/",
    "BSC官方11": "https://bsc-dataseed2.binance.org/",
    "BSC官方12": "https://bsc-dataseed3.binance.org/",
    "BSC官方13": "https://bsc-dataseed4.binance.org/",
    
    # 公共节点
    "1RPC": "https://1rpc.io/bnb",
    "PublicNode": "https://bsc.publicnode.com",
    "OnFinality": "https://bsc.publicnode.com",
    "BSCArchive": "https://bsc-archive.allthatnode.com:8545",
    "BSCArchive2": "https://bsc-archive2.allthatnode.com:8545",
    "BSCArchive3": "https://bsc-archive3.allthatnode.com:8545",
    "BSCArchive4": "https://bsc-archive4.allthatnode.com:8545",
    "BSCArchive5": "https://bsc-archive5.allthatnode.com:8545",
    "BSCArchive6": "https://bsc-archive6.allthatnode.com:8545",
    "BSCArchive7": "https://bsc-archive7.allthatnode.com:8545",
    "BSCArchive8": "https://bsc-archive8.allthatnode.com:8545",
    "BSCArchive9": "https://bsc-archive9.allthatnode.com:8545",
    "BSCArchive10": "https://bsc-archive10.allthatnode.com:8545"
}

def test_node(node_name, node_url):
    """测试单个节点的响应时间"""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 1
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        start_time = time.time()
        response = requests.post(node_url, json=payload, headers=headers, timeout=10)
        end_time = time.time()
        
        if response.status_code == 200:
            response_time = (end_time - start_time) * 1000  # 转换为毫秒
            return {
                "node": node_name,
                "status": "成功",
                "response_time": round(response_time, 2),
                "block_number": int(response.json()["result"], 16)
            }
        else:
            return {
                "node": node_name,
                "status": "失败",
                "error": f"HTTP错误: {response.status_code}"
            }
    except Exception as e:
        return {
            "node": node_name,
            "status": "失败",
            "error": str(e)
        }

def main():
    print("开始测试BSC节点响应速度...\n")
    
    # 使用线程池并行测试所有节点
    with ThreadPoolExecutor(max_workers=len(NODES)) as executor:
        futures = [
            executor.submit(test_node, name, url)
            for name, url in NODES.items()
        ]
        
        results = [future.result() for future in futures]
    
    # 按响应时间排序（成功的节点）
    successful_results = [r for r in results if r["status"] == "成功"]
    successful_results.sort(key=lambda x: x["response_time"])
    
    # 打印结果
    print("\n=== 速度最快的5个节点 ===")
    print("-" * 80)
    
    # 只打印前5个最快的节点
    for index, result in enumerate(successful_results[:5], 1):
        print(f"第{index}名")
        print(f"节点: {result['node']}")
        print(f"响应时间: {result['response_time']}ms")
        print(f"当前区块: {result['block_number']}")
        print("-" * 80)
    
    # 打印统计信息
    print("\n=== 统计信息 ===")
    print(f"总节点数: {len(results)}")
    print(f"成功节点数: {len(successful_results)}")
    print(f"失败节点数: {len(results) - len(successful_results)}")
    if successful_results:
        print(f"最快节点: {successful_results[0]['node']} ({successful_results[0]['response_time']}ms)")
        print(f"最慢节点: {successful_results[-1]['node']} ({successful_results[-1]['response_time']}ms)")
        avg_time = sum(r['response_time'] for r in successful_results) / len(successful_results)
        print(f"平均响应时间: {round(avg_time, 2)}ms")

if __name__ == "__main__":
    main() 