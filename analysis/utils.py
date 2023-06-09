import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from pycoingecko import CoinGeckoAPI
from dotenv import load_dotenv

# 副程式：取得 Tokenlon Subgraph 的 Query
def get_tokenlon_graphql_query(gte_timestamp, skip):
    return f"""{{
  swappeds(
    first: 1000
    skip: {skip}
    orderBy: timestamp
    orderDirection: desc
    where: {{timestamp_gte: {gte_timestamp}}}
  ) {{
    id
    blockNumber
    timestamp
    makerAssetAddr
    settleAmount
    takerAssetAddr
    takerAssetAmount
  }}
  fillOrders(
    first: 1000
    skip: {skip}
    orderBy: timestamp
    orderDirection: desc
    where: {{timestamp_gte: {gte_timestamp}}}
  ) {{
    id
    blockNumber
    timestamp
    makerAssetAddr
    settleAmount
    takerAssetAddr
    takerAssetAmount
  }}
  limitOrders(
    first: 1000
    skip: {skip}
    orderBy: blockTimestamp
    orderDirection: desc
    where: {{blockTimestamp_gte: "{gte_timestamp}"}}
  ) {{
    id
    blockNumber
    blockTimestamp
    makerToken
    makerTokenFilledAmount
    takerToken
    takerTokenFilledAmount
    limitOrderType
  }}
}}"""

# 副程式：從 The Graph 中取出
def get_tokenlon_data(skip):
    # 從 .env 檔案取得 GRAPH_URL 參數
    load_dotenv()
    GRAPH_URL = os.getenv("GRAPH_URL")
    # 計算 90 天前的 timestamp
    days_90_timestamp = int((datetime.now() - timedelta(days=90)).timestamp())
    query = get_tokenlon_graphql_query(days_90_timestamp, skip)
    # 建立 GraphQL query 的請求
    r = requests.post(GRAPH_URL, json={'query': query})
    print('Note: Use The Tokenlon Graph API')
    # 從回傳的結果中提取出需要的資料
    query_data = json.loads(r.text)['data']
    # 取出 swappeds，重新命名，並增加一個 method 欄位，均存放 amm 字串值
    swappeds = pd.DataFrame(query_data['swappeds'], columns=["id", "blockNumber", "timestamp", "makerAssetAddr", "settleAmount", "takerAssetAddr", "takerAssetAmount"])
    swappeds = swappeds.rename(columns={"id": "Id", "blockNumber": "BlockNumber", "timestamp": "Timestamp", "makerAssetAddr": "MakerToken", "settleAmount": "MakerAmount", "takerAssetAddr": "TakerToken", "takerAssetAmount": "TakerAmount"})
    swappeds = swappeds.assign(Method="amm")
    # 取出 fillOrders，並增加一個 method 欄位，均存放 pmmOrRfq 字串值
    fillOrders = pd.DataFrame(query_data['fillOrders'], columns=["id", "blockNumber", "timestamp", "makerAssetAddr", "settleAmount", "takerAssetAddr", "takerAssetAmount"])
    fillOrders = fillOrders.rename(columns={"id": "Id", "blockNumber": "BlockNumber", "timestamp": "Timestamp", "makerAssetAddr": "MakerToken", "settleAmount": "MakerAmount", "takerAssetAddr": "TakerToken", "takerAssetAmount": "TakerAmount"})
    fillOrders = fillOrders.assign(Method="pmmOrRfq")
    # 取出 limitOrders，並自帶一個 method 欄位，存放 limitOrderType
    limitOrders = pd.DataFrame(query_data['limitOrders'], columns=["id", "blockNumber", "blockTimestamp", "makerToken", "makerTokenFilledAmount", "takerToken", "takerTokenFilledAmount", "limitOrderType"])
    limitOrders = limitOrders.rename(columns={"id": "Id", "blockNumber": "BlockNumber", "blockTimestamp": "Timestamp", "makerToken": "MakerToken", "makerTokenFilledAmount": "MakerAmount", "takerToken": "TakerToken", "takerTokenFilledAmount": "TakerAmount", "limitOrderType": "Method"})
    # 將這 3 個變數組合在一起，並使用 Timestamp 進行遞增排序
    merged_data = pd.concat([swappeds, fillOrders, limitOrders], ignore_index=True)
    merged_data["Timestamp"] = merged_data["Timestamp"].astype(int)
    return merged_data.sort_values(by="Timestamp", ascending=True)

# 將 subgraph_price 的 Timestamp 對 coingecko_price 搜尋最靠近的 Price 值
# 並寫入 subgraph_price 第 3 個 CoingeckoPrice Column 中
def add_nearest_price_column(coingecko_price, subgraph_price):
    def find_nearest_price(timestamp):
        nearest_timestamp = coingecko_price['Timestamp'].iloc[(coingecko_price['Timestamp']-timestamp).abs().argsort()[0]]
        nearest_price = coingecko_price.loc[coingecko_price['Timestamp'] == nearest_timestamp, 'Price'].iloc[0]
        return nearest_price
    subgraph_price['CoingeckoPrice'] = subgraph_price['Timestamp'].apply(find_nearest_price)
    return subgraph_price

# 副程式：取得 Tokenlon Subgraph 的 Query
def get_uniswap3_graphql_query(gte_timestamp, skip):
    return f"""{{
  tokenHourDatas(
    first: 1000
    skip: {skip}
    orderBy: periodStartUnix
    where: {{token_: {{symbol: "WETH"}}, periodStartUnix_gte: {gte_timestamp}}}
    orderDirection: desc
  ) {{
    id
    periodStartUnix
    open
    high
    low
    close
  }}
}}"""

def get_uniswap3_data(skip):
    # 計算 90 天前的 timestamp
    days_90_timestamp = int((datetime.now() - timedelta(days=90)).timestamp())
    query = get_uniswap3_graphql_query(days_90_timestamp, skip)
    # 建立 GraphQL query 的請求
    r = requests.post("https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3", json={'query': query})
    print('Note: Use The Uniswap V3 Graph API')
    # 從回傳的結果中提取出需要的資料
    query_data = json.loads(r.text)['data']
    tokenHourDatas = pd.json_normalize(query_data)
    # 取出 tokenHourDatas
    tokenHourDatas = pd.DataFrame(query_data['tokenHourDatas'], columns=["id", "periodStartUnix", "open", "high", "low", "close"])
    # 取出 id 的「-」前面的值，即為 Token Address 值
    tokenHourDatas['id'] = tokenHourDatas['id'].str.split('-').str[0]
    # 將 Header 重新命名
    tokenHourDatas = tokenHourDatas.rename(columns={"id": "Id", "periodStartUnix": "Timestamp", "open": "Open", "high": "High", "low": "Low", "close": "Close"})
    # 增加一個從 Close 複製來的 Price 值
    tokenHourDatas = tokenHourDatas.assign(Price=tokenHourDatas['Close'])
    return tokenHourDatas.sort_values(by="Timestamp", ascending=True)

# 副程式：取出 Price 資料後，將 Price 資料倒數
def reciprocal(data):
    data['Price'] = 1 / data['Price']
    return data

# 副程式：直接將輸入的 timestamps, prices 資料繪製出來
def plot(name, data):
    # 取得時間戳記和價格的列表
    timestamps, prices = zip(*zip(data['Timestamp'], data['Price']))
    # 創建圖表
    fig, ax = plt.subplots()
    # 設置圖表標題
    ax.set_title(name)
    # 設置 x 軸標籤
    ax.set_xlabel('Timestamp')
    # 設置 y 軸標籤
    ax.set_ylabel('Price (USD)')
    # 繪製折線圖
    ax.plot(timestamps, prices)
    # 顯示圖表
    plt.show()

# 繪製圖形，並透過滑鼠位置更新圖片上的 Price 資訊
def plotMove(name, data):
    timestamps, prices, coingeckoPrices = zip(*zip(data['Timestamp'], data['Price'], data['CoingeckoPrice']))
    fig, ax = plt.subplots()
    ax.set_title(name)
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Price (USD)')
    ax.plot(timestamps, prices, color='red', label='Price')
    ax.plot(timestamps, coingeckoPrices, color='blue', label='Coingecko Price')
    ax.legend()
    # 定義事件處理器
    def on_move(event):
        if event.inaxes == ax:
            x, y = event.xdata, event.ydata
            # 尋找最接近滑鼠位置的點
            index = min(range(len(timestamps)), key=lambda i: abs(timestamps[i]-x))
            # 將 Timestamp 轉成人類看得懂的型式
            time = datetime.fromtimestamp(timestamps[index]).strftime('%Y-%m-%d %H:%M:%S')
            price = prices[index]
            coingeckoPrice = coingeckoPrices[index]
            # 更新標題顯示價格
            ax.set_title(f'{name} Time: {time}\nPrice: {price:.6f}, CoingeckoPrice: {coingeckoPrice:.6f}')
            fig.canvas.draw()
    # 綁定事件處理器
    fig.canvas.mpl_connect('motion_notify_event', on_move)
    # 將 Y 軸的顯示範圍為 prices 的 3 倍標準差內的最小／大值
    price_min, price_max = filtered_prices_max(prices)
    coingeckoPrices_min, coingeckoPrices_max = filtered_prices_max(coingeckoPrices)
    plt.ylim(min(price_min, coingeckoPrices_min), max(price_max, coingeckoPrices_max))
    # 繪圖
    plt.show()

# 繪製圖形，並透過滑鼠位置更新圖片上的 Price 資訊
def plotMove2(name, coingecko_data, sell_coin_data, buy_coin_data):
    # 只要留下 coingecko_data 的 Timestamp 大於 sell_coin_data 或 buy_coin_data 內的資料
    min_timestamp = min(min(sell_coin_data['Timestamp']), min(buy_coin_data['Timestamp']))
    last_index = (coingecko_data['Timestamp'] >= min_timestamp).idxmax() - 1
    coingecko_data = coingecko_data.iloc[last_index:]
    print(coingecko_data)
    # 將資料轉成繪圖可以使用的格式
    coingecko_timestamps, coingecko_prices = zip(*zip(coingecko_data['Timestamp'], coingecko_data['Price']))
    sell_timestamps, sell_prices, sell_coingeckoPrices = zip(*zip(sell_coin_data['Timestamp'], sell_coin_data['Price'], sell_coin_data['CoingeckoPrice']))
    buy_timestamps, buy_prices, buy_coingeckoPrices = zip(*zip(buy_coin_data['Timestamp'], buy_coin_data['Price'], buy_coin_data['CoingeckoPrice']))
    fig, ax = plt.subplots()
    ax.set_title(name)
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Price (USD)')
    ax.plot(buy_timestamps, buy_prices, color='blue', label='Buy Price')
    ax.plot(sell_timestamps, sell_prices, color='red', label='Sell Price')
    ax.plot(coingecko_timestamps, coingecko_prices, color='green', label='Coingecko Price')
    # ax.plot(coingecko_timestamps, coingecko_prices, color='green', label='Uniswap V3 Price')
    ax.legend()
    def on_move(event):
        # 判斷滑鼠事件發生在 ax 這個子圖上
        if event.inaxes == ax:
            # 取得滑鼠位置
            x, y = event.xdata, event.ydata        
            # 計算距離每條線的距離
            sell_distance = abs(y - np.interp(x, sell_timestamps, sell_prices))
            buy_distance = abs(y - np.interp(x, buy_timestamps, buy_prices))
            # 取得最近的線
            min_distance = min(sell_distance, buy_distance)
            # 判斷最近的線是 buy 線還是 sell 線
            if min_distance == sell_distance:
                timestamps = sell_timestamps
                prices = sell_prices
                coingeckoPrices = sell_coingeckoPrices
                line_name = 'Sell'
            else:
                timestamps = buy_timestamps
                prices = buy_prices
                coingeckoPrices = buy_coingeckoPrices
                line_name = 'Buy'
            # 取得最近的點的索引值和座標值
            index = np.argmin(np.abs(timestamps - x))
            timestamp_value = timestamps[index]
            # 將 Timestamp 轉成人類看得懂的型式
            time = datetime.fromtimestamp(timestamp_value).strftime('%Y-%m-%d %H:%M:%S')
            # time = timestamp_value
            price_value = prices[index]
            coingeckoPrice_value = coingeckoPrices[index]
            # 更新圖表標題顯示 Price 和 Timestamp 值
            ax.set_title(f'{name} Time: {time}\n{line_name}: Price={price_value:.6f}, CoingeckoPrices={coingeckoPrice_value:.6f}')
            # ax.set_title(f'{name} Time: {time}\n{line_name}: Price={price_value:.6f}, Uniswap3Prices={coingeckoPrice_value:.6f}')
            fig.canvas.draw()
    # 綁定事件處理器
    fig.canvas.mpl_connect('motion_notify_event', on_move)
    # 將 Y 軸的顯示範圍為 prices 的 3 倍標準差內的最小／大值
    sell_price_min, sell_price_max = filtered_prices_max(sell_prices)
    buy_price_min, buy_price_max = filtered_prices_max(buy_prices)
    coingeckoPrices_min, coingeckoPrices_max = filtered_prices_max(coingecko_prices)
    plt.ylim(min(sell_price_min, buy_price_min, coingeckoPrices_min), max(sell_price_max, buy_price_max, coingeckoPrices_max))
    # 計算 1 天前的 timestamp
    days_timestamp = int((datetime.now() - timedelta(days=0.5)).timestamp())
    # 將 X 軸顯示範圍為 sell 或 buy 的 timestamp 顯示範圍
    # plt.xlim(min(min(sell_timestamps),min(buy_timestamps)), max(sell_timestamps))
    plt.xlim(days_timestamp, max(sell_timestamps))
    # 繪圖
    plt.show()

# 繪製圖形，並透過滑鼠位置更新圖片上的 Price 資訊
def plotMove3(name, coingecko_data, sell_coin_data, buy_coin_data):
    # 限制圖表顯示範圍
    # date_start = "2023/03/10 00:00:00+0800"
    # date_end = "2023/03/17 00:00:00+0800"
    # date_start = "2023/03/15 00:00:00+0800"
    # date_end = "2023/03/18 00:00:00+0800"
    date_start = "2023/03/20 00:00:00+0800"
    date_end = "2023/03/23 00:00:00+0800"
    # 設置時間刻度
    locator = mdates.HourLocator(interval=6)  # 每小时一个刻度
    formatter = mdates.DateFormatter('%m/%d %H:%M')  # 以小时和分钟的形式显示时间
    # locator = mdates.DayLocator(interval=1)  # 每天一个刻度
    # formatter = mdates.DateFormatter('%m/%d')  # 以月和日的形式显示时间    
    # 将字符串转换为datetime对象，以及将datetime对象转换为Unix时间戳
    timestamp_start = int(datetime.strptime(date_start, "%Y/%m/%d %H:%M:%S%z").timestamp())
    timestamp_end = int(datetime.strptime(date_end, "%Y/%m/%d %H:%M:%S%z").timestamp())
    # 以 date_start 及 date_end 篩選資料來源
    coingecko_data = coingecko_data[(coingecko_data['Timestamp'] >= timestamp_start) & (coingecko_data['Timestamp'] <= timestamp_end)]
    sell_coin_data = sell_coin_data[(sell_coin_data['Timestamp'] >= timestamp_start) & (sell_coin_data['Timestamp'] <= timestamp_end)]
    buy_coin_data = buy_coin_data[(buy_coin_data['Timestamp'] >= timestamp_start) & (buy_coin_data['Timestamp'] <= timestamp_end)]
    # 將資料轉成繪圖可以使用的格式
    coingecko_timestamps, coingecko_prices = zip(*zip(coingecko_data['Timestamp'], coingecko_data['Price']))
    sell_timestamps, sell_prices, sell_coingeckoPrices = zip(*zip(sell_coin_data['Timestamp'], sell_coin_data['Price'], sell_coin_data['CoingeckoPrice']))
    buy_timestamps, buy_prices, buy_coingeckoPrices = zip(*zip(buy_coin_data['Timestamp'], buy_coin_data['Price'], buy_coin_data['CoingeckoPrice']))
    # 重新格式化时间戳
    coingecko_timestamps = [datetime.fromtimestamp(ts) for ts in coingecko_data['Timestamp']]
    sell_timestamps = [datetime.fromtimestamp(ts) for ts in sell_coin_data['Timestamp']]
    buy_timestamps = [datetime.fromtimestamp(ts) for ts in buy_coin_data['Timestamp']]
    # 建立繪圖物件
    fig, ax = plt.subplots()
    # 設定子圖之間的間距，可以通過調整 bottom 參數增加底部的空白
    fig.subplots_adjust(bottom=0.2)
    # 设置时间刻度
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.set_title(name)
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Price (USD)')
    ax.plot(buy_timestamps, buy_prices, color='blue', label='Buy Price')
    ax.plot(sell_timestamps, sell_prices, color='red', label='Sell Price')
    ax.plot(coingecko_timestamps, coingecko_prices, color='green', label='Coingecko Price')
    # ax.plot(coingecko_timestamps, coingecko_prices, color='green', label='Uniswap V3 Price')
    ax.legend()
    def on_move(event):
        # 判斷滑鼠事件發生在 ax 這個子圖上
        if event.inaxes == ax:
            # 取得滑鼠位置
            x, y = event.xdata, event.ydata        
            # 計算距離每條線的距離
            sell_distance = abs(y - np.interp(x, sell_timestamps, sell_prices))
            buy_distance = abs(y - np.interp(x, buy_timestamps, buy_prices))
            # 取得最近的線
            min_distance = min(sell_distance, buy_distance)
            # 判斷最近的線是 buy 線還是 sell 線
            if min_distance == sell_distance:
                timestamps = sell_timestamps
                prices = sell_prices
                coingeckoPrices = sell_coingeckoPrices
                line_name = 'Sell'
            else:
                timestamps = buy_timestamps
                prices = buy_prices
                coingeckoPrices = buy_coingeckoPrices
                line_name = 'Buy'
            # 取得最近的點的索引值和座標值
            index = np.argmin(np.abs(timestamps - x))
            timestamp_value = timestamps[index]
            # 將 Timestamp 轉成人類看得懂的型式
            time = datetime.fromtimestamp(timestamp_value).strftime('%Y-%m-%d %H:%M:%S')
            # time = timestamp_value
            price_value = prices[index]
            coingeckoPrice_value = coingeckoPrices[index]
            # 更新圖表標題顯示 Price 和 Timestamp 值
            ax.set_title(f'{name} Time: {time}\n{line_name}: Price={price_value:.6f}, CoingeckoPrices={coingeckoPrice_value:.6f}')
            # ax.set_title(f'{name} Time: {time}\n{line_name}: Price={price_value:.6f}, Uniswap3Prices={coingeckoPrice_value:.6f}')
            fig.canvas.draw()
    # 綁定事件處理器
    fig.canvas.mpl_connect('motion_notify_event', on_move)
    # 將 Y 軸的顯示範圍為 prices 的 3 倍標準差內的最小／大值
    sell_price_min, sell_price_max = filtered_prices_max(sell_prices)
    buy_price_min, buy_price_max = filtered_prices_max(buy_prices)
    coingeckoPrices_min, coingeckoPrices_max = filtered_prices_max(coingecko_prices)
    plt.ylim(min(sell_price_min, buy_price_min, coingeckoPrices_min), max(sell_price_max, buy_price_max, coingeckoPrices_max))
    # 將 X 軸顯示範圍為 sell 或 buy 的 timestamp 顯示範圍
    plt.xlim(min(min(sell_timestamps),min(buy_timestamps)), max(sell_timestamps))
    # 调整时间标签角度
    # plt.xticks(rotation=45)
    plt.xticks(rotation=45, ha='right', rotation_mode='anchor', va='top')
    # 繪圖
    plt.show()

# 從 CoinGecko 取得最新的 90 天資料（取得 1 ~ 90 天的資料，資料精細度僅可到「小時」
def get_coingecko_price(coin):
    # 初始化 CoinGeckoAPI
    cg = CoinGeckoAPI()
    # 從 CoinGecko 取得最新資料
    coin_usd_data = cg.get_coin_market_chart_by_id(id=coin, vs_currency='usd', days=90, interval='only daily can use', localization = False)
    print('Note: Use CoinGecko API')
    # 取得 prices 欄位
    coin_usd_price = coin_usd_data['prices']
    # 將數據轉換為 Pandas DataFrame
    return pd.DataFrame(coin_usd_price, columns=['Timestamp', 'Price'])

# 定義函式：檢查是否存在 CSV 檔案
def check_csv_file(csv_file_path):
    if os.path.exists(csv_file_path):
        return True
    else:
        return False

def get_last_time(csv_file_path):
    last_timestamp = 0
    # 檢查是否存在 CSV 檔案，以及最新資料的時間和現在的時間之間的差距
    if check_csv_file(csv_file_path):
        coin_data_csv = pd.read_csv(csv_file_path, parse_dates=False)
        last_timestamp = coin_data_csv['Timestamp'].iloc[-1]
    return last_timestamp

def update_csv(csv_file_path, data):
    if not check_csv_file(csv_file_path):
        raise ValueError("CSV file must be exist")
    # 從 CSV 中取得最後的 Timestamp
    last_timestamp = get_last_time(csv_file_path)
    # 只要從 CoinGecko 篩出 csv 裡沒有的資料就好
    data_new = data[data['Timestamp'] > last_timestamp]
    # 數據加入到原有檔案中
    data_new.to_csv(csv_file_path, mode='a', header=False, index=False)

# 定義函式：計算最新資料的時間和現在的時間之間的差距
# def get_time_diff(eth_usd_data_csv):
#     last_data_time_str = eth_usd_data_csv['Timestamp'].iloc[-1]
#     last_data_time = datetime.strptime(last_data_time_str, '%Y-%m-%d %H:%M:%S')
#     # 計算最新資料的時間和現在的時間之間的差距
#     now_time = datetime.now()
#     time_diff = (now_time - last_data_time).total_seconds() / 3600  # 單位轉換為小時
#     return time_diff

# 取得 prices 的 n 倍標準差內的最小／大值
def filtered_prices_max(prices):
    n = 2
    # 計算平均值和標準差
    mean = np.mean(prices)
    std = np.std(prices)
    # 計算上限和下限
    upper_bound = mean + n * std
    lower_bound = mean - n * std
    # 篩選出在 4 倍標準差內的數值
    filtered_prices = [price for price in prices if lower_bound <= price <= upper_bound]
    # filtered_prices = df[(df['Price'] >= lower_bound) & (df['Price'] <= upper_bound)]['Price']
    # 取得最大值
    return min(filtered_prices), max(filtered_prices)

# 取得 prices 的 n 倍標準差內的最小／大值
def over_n_std_to_df(input):
    data = input[['Timestamp', 'Price']].copy()
    n = 2
    # 計算平均值和標準差
    mean = data['Price'].mean()
    std = data['Price'].std()
    # 計算上限和下限
    upper_bound = mean + n * std
    lower_bound = mean - n * std
    # 假設你的 DataFrame 名稱為 df，欄位名稱分別為 Timestamp 和 Price
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], unit='s')  # 假設 Timestamp 單位為秒，使用 unit='s' 轉換
    data = data[data['Price'] > upper_bound]
    data_date = data[['Timestamp']].copy()
    data_date['Timestamp'] = data_date['Timestamp'].dt.date  # 新增 Date 欄位，只保留日期部份
    grouped = data_date.groupby('Timestamp').size()  # 將 DataFrame 按照日期分組，並計算每個日期的個數
    # plt.bar(grouped.index, grouped.values)  # 顯示長條圖
    # plt.xlabel('Date')
    # plt.ylabel('Count')
    # plt.xticks(rotation=45)
    # plt.show()
    fig, ax = plt.subplots()
    ax.bar(grouped.index, grouped.values)  # 顯示長條圖

    # 設定 x 軸標籤的日期格式
    date_fmt = mdates.DateFormatter('%m/%d')
    ax.xaxis.set_major_formatter(date_fmt)

    # 設定 x 軸標籤的日期間隔
    locator = mdates.DayLocator(interval=2)  # 每天一个刻度
    # locator = mdates.AutoDateLocator()
    # locator.intervald[1] = 1  # 將預設的日期間隔調整為 1 天
    ax.xaxis.set_major_locator(locator)
    plt.xticks(rotation=45, ha='right', rotation_mode='anchor', va='top')
    plt.xlabel('Date')
    plt.ylabel('Count')
    plt.show()
    return data
