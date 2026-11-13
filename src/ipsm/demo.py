"""Synthetic desktop for offline UI verification; contains no device data."""
from .i18n import tr


def demo_state() -> list:
    def app(name: str, number: int) -> dict:
        return {"displayName": name, "displayIdentifier": f"example.demo.app{number}"}

    names = ["电话", "浏览器", "信息", "音乐", "日历", "照片", "相机", "地图", "时钟",
             "备忘录", "提醒事项", "天气", "阅读", "播客", "钱包", "设置", "邮件", "健康",
             "翻译", "文件", "计算器", "指南针", "出行", "旅行", "工作", "学习", "生活", "购物"]
    apps = [app(name, i) for i, name in enumerate(names)]
    folder = {"displayName": tr("도구"), "listType": "folder", "iconLists": [apps[20:24]]}
    return [apps[:4], apps[4:16] + [folder], apps[16:20] + apps[24:]]
