# Orange 本地工作台｜分享版

这是一个可直接复制给朋友使用的独立 Windows 版本，包含：项目管理、备忘录、LP 流动性、交易记录、常用代币合约和聪明钱地址。

发布包只包含空白数据模板，不包含制作者的仓位、交易、备忘录、代币合约、钱包地址、密钥或 WSL 路径。所有新记录默认保存在本文件夹的 `data` 目录。

## 启动

1. Windows 安装 Python 3（安装时勾选 **Add Python to PATH**）。
2. 双击 `start_windows.bat`。
3. 首次启动会联网安装 Flask，随后自动打开 `http://127.0.0.1:8084`。
4. 启动窗口需要保持打开；在窗口中按 `Ctrl+C` 即可停止。

若启动窗口已经关闭但端口仍被占用，可双击 `stop_windows.bat`。

## 更换端口

8084 被占用时，在 PowerShell 中执行：

```powershell
cd "本文件夹路径"
$env:WORKTABLE_PORT="8090"
.\start_windows.bat
```

访问地址随之变为 `http://127.0.0.1:8090`。停止该端口时，在同一 PowerShell 窗口执行 `stop_windows.bat`。

## 数据与备份

- `data/projects_data.json`：项目及 LP 账本
- `data/memos_data.json`：备忘录
- `data/trade_log_data.json`：交易记录
- `data/token_contracts.json`：代币合约
- `data/smart_wallets.json`：聪明钱地址

备份时关闭工作台，然后复制整个 `data` 文件夹。升级程序前也建议先备份此文件夹。

## 可选：同步外部 LP 数据文件

默认不开启任何外部同步。如需让 LP 模块与另一个同格式 JSON 文件双向同步，可在启动前设置：

```powershell
$env:WORKBENCH_LP_SOURCE_FILE="D:\路径\projects_data.json"
.\start_windows.bat
```

外部文件是主数据源；写入前请自行备份。不要把 API 密钥、私钥或助记词写入 JSON。

## 可选：DeBank 资产快照

聪明钱页面可手工记录地址。若持有 DeBank Pro API AccessKey，可在启动前设置：

```powershell
$env:DEBANK_ACCESS_KEY="你的 AccessKey"
.\start_windows.bat
```

AccessKey 只从当前环境变量读取，不会写入页面或数据文件。

## 分享前检查

如果朋友使用一段时间后还要再次转发，请先确认 `data` 文件夹里没有不希望分享的记录。若要制作新的空白副本，用本发布包原件重新复制，不要直接发送已使用过的目录。
