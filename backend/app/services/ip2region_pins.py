"""ip2region 版本信任清单：仅清单内版本的 xdb 文件允许安装。

运行期自动更新从公开仓库下载“最新版本”，结构校验无法抵御上游仓库被篡改或
供应链投毒。此清单把运行期可接受的 (版本, 文件) → SHA256 固定下来：
- 未列入清单的新版本一律拒绝安装（宁可停止更新，也不装入未经审计的数据）；
- 列入清单的版本还会校验下载文件哈希，防传输篡改。

升级流程：上游发布新版本后，先用 `backend/scripts/download_ip2region.py
--tag <新版本>` 在可审计的构建流程中固定哈希，再把生成的两条记录加入本清单。
"""

PINNED_SHA256: dict[tuple[str, str], str] = {
    (
        "v3.17.0",
        "ip2region_v4.xdb",
    ): "6307a9696f5711f84bcb8b25f07894de68a64a0ed4a1cc7e990562dd3084f210",
    (
        "v3.17.0",
        "ip2region_v6.xdb",
    ): "5b93da35ac28bc316dccc54a758381f7a874ae0461dd51ff5df5e34815586f11",
}

# 构建期拉取的 Python 绑定源码固定哈希（相对 binding/python 的路径）。
# 本地 vendored backend/ip2region/ 供开发与测试使用，镜像内则在构建时按此清单拉取，
# 二者内容必须一致（test_ip2region_pins 会校验）。
BINDING_SHA256: dict[tuple[str, str], str] = {
    (
        "v3.17.0",
        "ip2region/__init__.py",
    ): "1cb7dfe6b8b19feff29bf9c9a3107b34ee856d19817a5ac1e464070ddb330b5d",
    (
        "v3.17.0",
        "ip2region/util.py",
    ): "eda5592a77007bf3a2cf4255a7eb7372cf57a7db844e5238231843bf3bfeab9e",
    (
        "v3.17.0",
        "ip2region/searcher.py",
    ): "621c93ae7a3bc858cef994b2ed99551550c3574fb0e6d537affd1b4458d9a0d8",
    (
        "v3.17.0",
        "LICENSE",
    ): "4416735adc725546aea1d352879eac20932e76bc3050a4c81ec9fa6a3a3a125c",
}
