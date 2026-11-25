# legacy —— 旧版存档

这里放 v1.0 / v2.0 的单文件实现，只作历史参考，不参与打包、测试与 CI。

| 文件 | 版本 | 说明 |
|---|---|---|
| `ChatSplit-v1.0.py` | v1.0 | 早期单文件版，纯规则切分 |
| `ChatSplit-v2.0.py` | v2.0 | 单文件整理版，已有结构保护与颜文字匹配 |

**注意：这两个脚本目前跑不起来。** 它们都按脚本同级的 `Kaomoji/kaomojis.txt`
读取语料（见文件里的 `KAOMOJI_FILE`），该路径已随仓库整理消失——语料现在在
`qikou/kaomojis.txt`。要复跑旧版，把语料复制成 `legacy/Kaomoji/kaomojis.txt`，
或直接改脚本里的 `KAOMOJI_FILE` 常量。

现行实现见 `../qikou/`，命令行入口 `qikou`。
