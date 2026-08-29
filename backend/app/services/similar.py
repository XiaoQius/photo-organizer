"""相似媒体分组：图片用 BK-tree（汉明距离半径查询，可扩展到大库），视频用逐帧签名比对。"""

from app.config import PHASH_DISTANCE_THRESHOLD, VIDEO_PHASH_DISTANCE_THRESHOLD, VIDEO_PHASH_MAX_COMPARE
from app.services.hashing import hamming_distance
from app.services.video_hash import video_distance


class BKTree:
    """ Burkhard-Keller 树：以汉明距离为度量的快速近邻查询。"""

    def __init__(self, items: list[tuple[int, object]]):
        # 节点: [key, payload, {distance: child_node}]
        self._root = None
        for key, payload in items:
            self._insert(key, payload)

    def _insert(self, key: int, payload: object):
        node = self._root
        if node is None:
            self._root = [key, payload, {}]
            return
        while True:
            dist = bin(key ^ node[0]).count("1")
            if dist == 0:
                node[1] = payload  # 同哈希：覆盖（外部已按 id 去重，理论上不发生）
                return
            child = node[2].get(dist)
            if child is None:
                node[2][dist] = [key, payload, {}]
                return
            node = child

    def query(self, key: int, radius: int) -> list[object]:
        results: list[object] = []
        if self._root is None:
            return results
        stack = [self._root]
        while stack:
            node = stack.pop()
            dist = bin(key ^ node[0]).count("1")
            if dist <= radius:
                results.append(node[1])
            for d, child in node[2].items():
                if dist - radius <= d <= dist + radius:
                    stack.append(child)
        return results


def group_similar_images(photos: list) -> list[list]:
    """photos 为带 16 位十六进制 phash 的图片对象列表，返回相似分组。"""
    hashed = [m for m in photos if m.phash and len(m.phash) == 16]
    if not hashed:
        return []
    tree = BKTree([(int(m.phash, 16), m) for m in hashed])
    used: set[int] = set()
    groups: list[list] = []
    for m in hashed:
        if m.id in used:
            continue
        nearby = tree.query(int(m.phash, 16), PHASH_DISTANCE_THRESHOLD)
        group = [m]
        used.add(m.id)
        for other in nearby:
            if other.id != m.id and other.id not in used:
                if hamming_distance(m.phash, other.phash) <= PHASH_DISTANCE_THRESHOLD:
                    group.append(other)
                    used.add(other.id)
        if len(group) > 1:
            groups.append(sorted(group, key=lambda x: x.path))
    return groups


def group_similar_videos(videos: list) -> list[list]:
    """videos 为带 48 位三帧签名 phash 的视频对象列表。"""
    hashed = [m for m in videos if m.phash and len(m.phash) == 48]
    if not hashed or len(hashed) > VIDEO_PHASH_MAX_COMPARE:
        return []
    used: set[int] = set()
    groups: list[list] = []
    for i, m in enumerate(hashed):
        if m.id in used:
            continue
        group = [m]
        used.add(m.id)
        for other in hashed[i + 1:]:
            if other.id in used:
                continue
            d = video_distance(m.phash, other.phash)
            if d is not None and d <= VIDEO_PHASH_DISTANCE_THRESHOLD:
                group.append(other)
                used.add(other.id)
        if len(group) > 1:
            groups.append(sorted(group, key=lambda x: x.path))
    return groups
