# ChatGPTelegramBot


## 功能

- [x] 在 Telegram 上与 ChatGPT 对话
- [x] 重置对话
- [x] 私人/群组对话 `(在群组或者私人每个人都是单独的一个会话，多个会话不会相互干扰)`

## 使用方法

- 安装 [Redis](https://redis.io/)

  您可以参考 [Redis 安装教程](https://www.google.com/search?q=Redis%E5%AE%89%E8%A3%85%E6%95%99%E7%A8%8B)

- 修改文件后缀 `config.json.example` 为 `config.json`

  根据文件内提示修改 `config.json` 配置文件

- 安装依赖
  ```
  pip3 install -r requirements.txt
  ```
  
  第一次安装 playwright 请使用 `playwright install`

- 运行 Telegram Bot 模块
  
  ```
  python3 bot.py
  ```

## 命令列表

```
start - 开始
help - 使用帮助
rechat - 重置对话
addwhite - 添加白名单
```

## 感谢 [acheong08/ChatGPT](https://github.com/acheong08/ChatGPT)
