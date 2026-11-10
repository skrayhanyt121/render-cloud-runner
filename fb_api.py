import json
import os
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

class FacebookAPI:
    def __init__(self, config_path: str = CONFIG_PATH):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.page_id = self.config["page_id"]
        self.page_token = self.config["page_access_token"]
        self.version = self.config.get("graph_version", "v20.0")
        self.base_url = f"https://graph.facebook.com/{self.version}"

    def _request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = {"access_token": self.page_token}
        if method == "GET" and data:
            params.update(data)
            url = f"{self.base_url}/{endpoint}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, method="GET")
            body = None
        else:
            url = f"{self.base_url}/{endpoint}"
            post_params = {"access_token": self.page_token}
            if data:
                post_params.update(data)
            body = urllib.parse.urlencode(post_params).encode("utf-8")
            req = urllib.request.Request(url, data=body, method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            raise RuntimeError(f"FB API Error [{e.code}]: {err_msg}")

    def publish_post(self, message: str, link: Optional[str] = None) -> Dict[str, Any]:
        """Publish a text/link status update to the page."""
        payload = {"message": message}
        if link:
            payload["link"] = link
        return self._request(f"{self.page_id}/feed", method="POST", data=payload)

    def publish_photo(self, photo_url: str, caption: str = "") -> Dict[str, Any]:
        """Publish a photo via public image URL with a caption."""
        payload = {"url": photo_url, "caption": caption}
        return self._request(f"{self.page_id}/photos", method="POST", data=payload)

    def get_recent_posts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve recent posts from the page feed."""
        res = self._request(f"{self.page_id}/feed", method="GET", data={"limit": limit, "fields": "id,message,created_time,shares,comments.summary(true),reactions.summary(true)"})
        return res.get("data", [])

    def get_comments(self, post_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Get comments on a specific post."""
        res = self._request(f"{post_id}/comments", method="GET", data={"limit": limit, "fields": "id,from,message,created_time"})
        return res.get("data", [])

    def reply_comment(self, comment_id: str, message: str) -> Dict[str, Any]:
        """Reply to a comment on a post."""
        return self._request(f"{comment_id}/comments", method="POST", data={"message": message})

    def delete_post(self, post_id: str) -> Dict[str, Any]:
        """Delete a post from the page."""
        return self._request(f"{post_id}", method="DELETE")

    def get_page_info(self) -> Dict[str, Any]:
        """Fetch general page information."""
        return self._request(f"{self.page_id}", method="GET", data={"fields": "id,name,link,followers_count,fan_count"})
