
"""
言之有"品" - 爬虫服务
将原 c.py 改造成 FastAPI HTTP API 服务
运行: python -m uvicorn spider_service:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import time
from urllib.parse import parse_qs, urlencode

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
except ImportError:
    raise ImportError("需要安装: pip install drissionpage")

# ===== FastAPI 应用设置 =====
app = FastAPI(
    title="言之有品 - 爬虫服务",
    version="1.0",
    description="基于用户商品链接自动爬取京东评论"
)

# CORS 配置（允许扣子调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 数据模型 =====
class ReviewItem(BaseModel):
    review_content: str
    rating: int
    review_time: str
    product_model: str
    likes: int

class SpiderRequest(BaseModel):
    product_url: str  # 例: https://item.jd.com/10127955410850.html
    max_pages: int = 50  # 可选参数

class SpiderResponse(BaseModel):
    success: bool
    message: str
    reviews: List[ReviewItem] = []
    total_count: int = 0

# ===== 全局变量 =====
dp = None

def init_browser():
    """初始化浏览器（全局单例）"""
    global dp
    if dp is None:
        co = ChromiumOptions()
        # ⚠️ 根据你的电脑环境修改这两个路径
        co.set_browser_path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        co.set_local_port(9333)
        co.set_user_data_path(r'D:\chrome_debug_profile')
        dp = ChromiumPage(co)
    return dp

# ===== 爬虫核心函数（从 c.py 直接移植）=====

def fetch_page(dp, page_num, body_json, post_single, template_params):
    """翻页请求函数"""
    body_json['pageNum'] = str(page_num)
    body_json['pageSize'] = "20"
    body_json['isFirstRequest'] = "false"
    post_single['body'] = json.dumps(body_json, ensure_ascii=False)
    post_data_str = urlencode(post_single)

    js_code = """
    return new Promise((resolve) => {
        fetch("%s", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://item.jd.com/"
            },
            body: %s,
            credentials: "include"
        })
        .then(r => r.json())
        .then(data => resolve(JSON.stringify(data)))
        .catch(e => resolve("ERROR:" + e.toString()));
    });
    """ % (template_params['url'], json.dumps(post_data_str))

    return dp.run_js(js_code, as_expr=False)

def find_comment_list(obj):
    """递归查找评论列表"""
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and 'commentInfo' in obj[0]:
            return obj
        for item in obj:
            result = find_comment_list(item)
            if result:
                return result
    elif isinstance(obj, dict):
        for v in obj.values():
            result = find_comment_list(v)
            if result:
                return result
    return None

def parse_and_collect(raw_json_str, all_reviews, seen_keys):
    """解析评论数据"""
    try:
        data = json.loads(raw_json_str)
    except Exception as e:
        return -1

    if str(data.get('code')) != '0':
        return -1

    try:
        datas = data['result']['floors'][2]['data']
        if not datas or 'commentInfo' not in str(datas[0]):
            raise ValueError("路径内容不是评论")
    except Exception:
        datas = find_comment_list(data)

    if not datas:
        return 0

    count = 0
    for item in datas:
        try:
            info = item['commentInfo']
            key = info['userNickName'] + info['commentDate'] + info.get('commentData', '')[:10]
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            all_reviews.append({
                "review_content": info.get('commentData', ''),
                "rating": int(info['commentScore']) if info.get('commentScore') else 0,
                "review_time": info.get('commentDate', ''),
                "product_model": info.get('productSpecifications', ''),
                "likes": int(info['buyCount']) if info.get('buyCount') else 0
            })
            count += 1
        except (KeyError, TypeError):
            continue

    return count

# ===== API 端点 =====

@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "ok",
        "message": "言之有品 爬虫服务运行中 ✅",
        "docs": "访问 http://localhost:8000/docs 查看 API 文档"
    }

@app.post("/spider/fetch_reviews", response_model=SpiderResponse)
async def fetch_reviews(request: SpiderRequest) -> SpiderResponse:
    """
    爬虫主端点
    
    请求示例:
    {
        "product_url": "https://item.jd.com/10127955410850.html",
        "max_pages": 50
    }
    
    返回:
    {
        "success": true,
        "message": "✅ 爬取完成！共获取 100 条评论",
        "reviews": [...],
        "total_count": 100
    }
    """
    
    try:
        product_url = request.product_url.strip()
        max_pages = request.max_pages
        
        # ===== 第一步：打开页面，点评论，抓第一个真实请求 =====
        dp = init_browser()
        dp.listen.start('client.action')
        dp.get(product_url)
        time.sleep(3)

        # 点全部评价
        for sel in ['text=全部评价', 'text=全部', '.comment-filter-item']:
            try:
                btn = dp.ele(sel, timeout=3)
                if btn:
                    btn.scroll.to_see()
                    time.sleep(1)
                    btn.click()
                    break
            except:
                continue

        # 等第一个数据包，提取请求参数模板
        template_params = None
        for _ in range(20):
            resp = dp.listen.wait(timeout=10)
            if resp is None:
                break
            if not hasattr(resp, 'response') or resp.response is None:
                continue
            body = resp.response.body
            if isinstance(body, dict) and 'result' in body:
                req = resp.request
                template_params = {
                    'url': req.url,
                    'headers': dict(req.headers),
                    'postData': req.postData
                }
                break

        dp.listen.stop()

        if not template_params:
            return SpiderResponse(
                success=False,
                message="❌ 未能获取请求模板，可能网站有反爬虫或页面加载失败",
                reviews=[],
                total_count=0
            )

        # ===== 第二步：解析 postData，提取 body 参数 =====
        post_dict = parse_qs(template_params['postData'])
        post_single = {k: v[0] for k, v in post_dict.items()}
        body_json = json.loads(post_single['body'])

        # ===== 第三步：循环翻页爬取 =====
        seen_keys = set()
        all_reviews = []
        max_empty_pages = 5
        empty_count = 0

        for page in range(1, max_pages + 1):
            raw = fetch_page(dp, page, body_json, post_single, template_params)

            if raw is None or str(raw).startswith("ERROR"):
                empty_count += 1
            else:
                result = parse_and_collect(raw, all_reviews, seen_keys)
                if result > 0:
                    empty_count = 0
                else:
                    empty_count += 1

            if empty_count >= max_empty_pages:
                break

            time.sleep(0.5)

        return SpiderResponse(
            success=True,
            message=f"✅ 爬取完成！共获取 {len(all_reviews)} 条评论",
            reviews=all_reviews,
            total_count=len(all_reviews)
        )

    except Exception as e:
        return SpiderResponse(
            success=False,
            message=f"❌ 爬虫出错: {str(e)}",
            reviews=[],
            total_count=0
        )

if __name__ == "__main__":
    import uvicorn
    
    print("""
    ╔════════════════════════════════════════════════╗
    ║   言之有"品" - 爬虫服务启动                        ║
    ║                                                ║
    ║   📍 运行地址: http://127.0.0.1:8000          ║
    ║   📖 API文档: http://127.0.0.1:8000/docs      ║
    ║   🔗 爬虫接口: POST /spider/fetch_reviews      ║
    ║                                                ║
    ║   按 Ctrl+C 停止服务                           ║
    ╚════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
