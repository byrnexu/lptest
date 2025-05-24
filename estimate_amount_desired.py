import math

def estimate_liquidity_amounts(
    P, lower_price, upper_price, amount0_avail, amount1_avail
):
    # 输入验证
    if lower_price >= upper_price:
        raise ValueError("最低价格必须小于最高价格")
    
    if P <= 0 or lower_price <= 0 or upper_price <= 0:
        raise ValueError("所有价格必须为正数")
    
    if amount0_avail < 0 or amount1_avail < 0:
        raise ValueError("可用代币数量不能为负数")
    
    if P < lower_price or P > upper_price:
        raise ValueError("当前价格必须在最低价格和最高价格之间")
    
    sqrt_P = math.sqrt(P)
    sqrt_lower = math.sqrt(lower_price)
    sqrt_upper = math.sqrt(upper_price)
    
    # 计算每单位流动性所需的代币
    delta_x = (1 / sqrt_P) - (1 / sqrt_upper)
    delta_y = sqrt_P - sqrt_lower
    
    # 检查是否在有效范围内
    if delta_x <= 0 or delta_y <= 0:
        raise ValueError("价格范围无效，无法计算流动性")
    
    # 计算最大可能的流动性 L
    L_from_token0 = amount0_avail / delta_x
    L_from_token1 = amount1_avail / delta_y
    L = min(L_from_token0, L_from_token1)
    
    # 预估实际投入数量
    amount0 = L * delta_x
    amount1 = L * delta_y
    
    return amount0, amount1, L

# 测试用例
def test_estimate_liquidity_amounts():
    print("开始测试流动性计算...")
    
    # 正常情况测试
    try:
        amount0, amount1, L = estimate_liquidity_amounts(
            P=2000,
            lower_price=1500,
            upper_price=2500,
            amount0_avail=0.5,
            amount1_avail=1000
        )
        print(f"测试1 - 正常情况:")
        print(f"  投入 token0: {amount0:.6f}")
        print(f"  投入 token1: {amount1:.6f}")
        print(f"  流动性 L: {L:.6f}")
    except ValueError as e:
        print(f"测试1错误: {e}")
    
    # 反向价格测试
    try:
        amount0, amount1, L = estimate_liquidity_amounts(
            P=1/2000,
            lower_price=1/2500,
            upper_price=1/1500,
            amount0_avail=1000,
            amount1_avail=0.5
        )
        print(f"\n测试2 - 反向价格:")
        print(f"  投入 token0: {amount0:.6f}")
        print(f"  投入 token1: {amount1:.6f}")
        print(f"  流动性 L: {L:.6f}")
    except ValueError as e:
        print(f"测试2错误: {e}")
    
    # 边界条件测试
    try:
        amount0, amount1, L = estimate_liquidity_amounts(
            P=2000,
            lower_price=2000,
            upper_price=2500,
            amount0_avail=0.5,
            amount1_avail=1000
        )
        print(f"\n测试3 - 边界条件:")
        print(f"  投入 token0: {amount0:.6f}")
        print(f"  投入 token1: {amount1:.6f}")
        print(f"  流动性 L: {L:.6f}")
    except ValueError as e:
        print(f"测试3错误: {e}")
    
    print("\n测试完成")

if __name__ == "__main__":
    test_estimate_liquidity_amounts()
