import json
import time
from typing import Dict, List, Optional, Tuple

import requests

# 设置请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
}

# 重试设置
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒

def write_to_file(text: str, file_path: str = "F:\\awa.txt") -> None:
    """写入内容到文件"""
    try:
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(f"{text}\n")
    except IOError as e:
        print(f"文件写入失败: {e}")

def send_request(
    url: str, 
    method: str = "GET", 
    params: Optional[Dict] = None, 
    headers: Dict = HEADERS
) -> Optional[requests.Response]:
    """发送HTTP请求并处理重试逻辑"""
    for attempt in range(MAX_RETRIES):
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, json=params, headers=headers, timeout=10)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            response.raise_for_status()
            return response
        
        except requests.exceptions.HTTPError as err:
            print(f"HTTP错误 ({attempt+1}/{MAX_RETRIES}): {err}")
        except requests.exceptions.ConnectionError as err:
            print(f"连接错误 ({attempt+1}/{MAX_RETRIES}): {err}")
        except requests.exceptions.Timeout as err:
            print(f"请求超时 ({attempt+1}/{MAX_RETRIES}): {err}")
        except requests.exceptions.RequestException as err:
            print(f"请求异常 ({attempt+1}/{MAX_RETRIES}): {err}")
        
        # 如果不是最后一次尝试，等待后重试
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
    
    return None

def get_page_list() -> Tuple[List[str], List[str]]:
    """获取页面标题和ID列表"""
    url = "https://api.bilibili.com/x/native_page/dynamic/index"
    params = {"page_id": "169153", "jsonp": "jsonp"}
    
    response = send_request(url, "GET", params)
    if not response:
        return [], []
    
    try:
        data = response.json()
        page_items = data["data"]["cards"][2]["item"][0]["item"]
        
        titles = [item["title"] for item in page_items]
        item_ids = [item["item_id"] for item in page_items]
        
        # 反转列表顺序
        return titles[::-1], item_ids[::-1]
    
    except (KeyError, IndexError, TypeError) as e:
        print(f"解析页面列表失败: {e}")
        return [], []

def extract_video_info(url: str) -> Optional[Tuple[str, str]]:
    """从URL中提取视频ID和评论ID"""
    try:
        # 从URL中提取评论ID
        comment_id = url.split("=")[-1]
        
        # 从URL中提取视频ID
        start_idx = url.find("video/") + 6
        if start_idx == -1:  # 如果没有找到video/，尝试其他方式
            # 尝试从URL中直接提取BV号
            if "bilibili.com/video/" in url:
                parts = url.split("/")
                video_id = parts[-1].split("?")[0]
            else:
                return None
        else:
            end_idx = url.find("?", start_idx)
            video_id = url[start_idx:end_idx] if end_idx != -1 else url[start_idx:]
        
        return video_id, comment_id
    
    except Exception as e:
        print(f"提取视频信息失败: {e}")
        return None

def get_comment_content(video_id: str, comment_id: str) -> Optional[str]:
    """获取指定评论的内容"""
    url = f"https://api.bilibili.com/x/v2/reply/main"
    params = {
        "oid": video_id,
        "type": 1,
        "mode": 3,
        "pagination_str": '{"offset":""}',
        "plat": 1,
        "seek_rpid": "",
        "web_location": 1315875,
        "w_rid": "74ec8ad746ead90dca2c6a8888879887",
        "wts": int(time.time())
    }
    
    response = send_request(url, "GET", params)
    if not response:
        return None
    
    try:
        data = response.json()
        replies = data["data"]["replies"]
        
        for reply in replies:
            if str(reply["rpid"]) == comment_id:
                return reply["content"]["message"]
        
        print(f"未找到评论ID {comment_id} 的内容")
        return None
    
    except (KeyError, TypeError) as e:
        print(f"解析评论内容失败: {e}")
        return None

def process_page(title: str, item_id: str) -> None:
    """处理单个页面"""
    print(f"\n处理页面: {title}")
    write_to_file(f"\n{title}")
    
    url = f"https://api.bilibili.com/x/native_page/dynamic/inline?page_id={item_id}"
    response = send_request(url, "GET")
    if not response:
        return
    
    try:
        data = response.json()
        comment_cards = data["data"]["cards"]
    except (KeyError, json.JSONDecodeError) as e:
        print(f"解析评论卡片失败: {e}")
        return
    
    comment_count = 0
    processed_urls = set()  # 用于记录已处理的URL，避免重复
    
    for card in comment_cards:
        try:
            # 跳过页头部分
            if "item" not in card or not card["item"]:
                continue
                
            # 获取卡片中的URL
            uri = card["item"][0]["item"][0].get("uri")
            if not uri:
                continue
                
            # 跳过已处理的URL
            if uri in processed_urls:
                continue
            processed_urls.add(uri)
            
            # 提取视频信息
            video_info = extract_video_info(uri)
            if not video_info:
                print(f"无法从URL提取视频信息: {uri}")
                continue
                
            video_id, comment_id = video_info
            
            # 获取评论内容
            comment_content = get_comment_content(video_id, comment_id)
            if not comment_content:
                continue
                
            # 写入文件
            comment_count += 1
            write_to_file(f"{comment_count}. {comment_content}")
            
        except Exception as e:
            print(f"处理卡片时出错: {e}")
            continue

def main():
    """主函数"""
    # 获取页面列表
    titles, item_ids = get_page_list()
    
    # 处理每个页面
    for title, item_id in zip(titles, item_ids):
        process_page(title, item_id)

if __name__ == "__main__":
    main()
