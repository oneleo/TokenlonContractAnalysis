import utils
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from web3 import Web3
import matplotlib.pyplot as plt

# 來源
tokenlon_subgraph_file_path = './data/tokenlon_subgraph.csv'
# 目的
tokenlon_index_file_path = './data/tokenlon_transaction_index.csv'

# 因為 tokenlon_subgraph_file 必須存在
# 所以請先執行過「index_price.py」檔建立檔案後，再執行此程式
if not utils.check_csv_file(tokenlon_subgraph_file_path):
    raise ValueError("CSV file must be exist")

# 從 .env 檔案取得 GRAPH_URL 參數
load_dotenv()
ETHEREUM_NODE_URL = os.getenv("ETHEREUM_NODE_URL")

# 計算 days_n 天內的 Tx Index 值
days_n = 3

# 讀取已知的 Dataframe
known_df = pd.read_csv(tokenlon_subgraph_file_path)
# 從已知的Dataframe中選擇所需的列
new_df = known_df.loc[:, ['Id', 'BlockNumber', 'Timestamp']]

# 透過 Ethereum 節點取得此交易的交易 Index
web3 = Web3(Web3.HTTPProvider(ETHEREUM_NODE_URL))
def find_transaction_index(transactionHash):
    # 透過交易哈希來獲取交易物件
    tx = web3.eth.get_transaction(transactionHash)
    print('向 ETH 節點取資料')
    return tx["transactionIndex"]

# tokenlon_index_file 如果存在就不用再去向 Ethereum 節點取值了
if not utils.check_csv_file(tokenlon_index_file_path):
    # 計算 days_n 天前的 timestamp
    days_timestamp = int((datetime.now() - timedelta(days=days_n)).timestamp())
    new_df = new_df[new_df['Timestamp'] > days_timestamp]
    new_df = new_df.assign(Index=new_df['Id'].str.split('-').str[1].apply(find_transaction_index))
    # 將新的DataFrame存儲為csv文件
    new_df.to_csv(tokenlon_index_file_path, index=False)

# 從 CSV 中取得最後的 Timestamp（不含毫秒），並計算與 now 的時間差
last_timestamp = utils.get_last_time(tokenlon_index_file_path)
time_diff = datetime.now() - datetime.fromtimestamp(last_timestamp)

# 如果超過 1 小時，表示 CSV 檔太舊，需將 CSV 檔更新
if time_diff.total_seconds() > 3600:
    # 計算 days_n 天前的 timestamp
    days_timestamp = int((datetime.now() - timedelta(days=days_n)).timestamp())
    new_df = new_df[new_df['Timestamp'] > days_timestamp]
    # 再篩出需要更新的部份
    new_df = new_df[new_df['Timestamp'] > last_timestamp]
    # 再將剩下的資料向 ETH 節點要取
    new_df = new_df.assign(Index=new_df['Id'].str.split('-').str[1].apply(find_transaction_index))
    # 最後將資料加入至 CSV 下方
    new_df.to_csv(tokenlon_index_file_path, mode='a', header=False, index=False)

# 從 CSV 中取得資料
tokenlon_txIndex = pd.read_csv(tokenlon_index_file_path)

# 計算 bins 的最大值
max_txindex = tokenlon_txIndex['Index'].max()
bins = list(range(0, max_txindex + 41, 40))

# 將 TxIndex 按照 bins 分類
txindex_counts = pd.cut(tokenlon_txIndex['Index'], bins=bins).value_counts()

# 建立繪圖物件
fig, ax = plt.subplots()
# 設定子圖之間的間距，可以通過調整 bottom 參數增加底部的空白
fig.subplots_adjust(bottom=0.2)

# 繪製直方圖並標註數量
plt.hist(tokenlon_txIndex['Index'], bins=bins)
for i, count in enumerate(txindex_counts):
    plt.text((bins[i] + bins[i+1])/2, count+1, str(count), ha='center')

# 設置 X 軸刻度標籤
bin_centers = [(bins[i] + bins[i+1])/2 for i in range(len(bins)-1)]
bin_labels = [f'[{bins[i]}, {bins[i+1]})' for i in range(len(bins)-1)]
plt.xticks(bin_centers, bin_labels)

# 取出第一個及最後一個Timestamp
# 首先取出第一個及最後一個Timestamp，並轉成datetime型別
first_ts = pd.to_datetime(tokenlon_txIndex['Timestamp'].iloc[0], unit='s')
last_ts = pd.to_datetime(tokenlon_txIndex['Timestamp'].iloc[-1], unit='s')

# 將Timestamp格式轉成人類可讀的形式
first_ts_str = first_ts.strftime('%Y-%m-%d')
last_ts_str = last_ts.strftime('%Y-%m-%d')

# 設置圖表標題及軸標籤
plt.title(f'{first_ts_str} ~ {last_ts_str} TxIndex Info')
plt.xticks(rotation=45, ha='right', rotation_mode='anchor', va='top')
plt.xlabel('TxIndex')
plt.ylabel('Count')

# 顯示圖表
plt.show()
