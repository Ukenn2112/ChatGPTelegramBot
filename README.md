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

- 运行 Telegram Bot 模块
  
  ```
  python3 bot.py
  ```

## 使用 Docker

> 使用 `Xvfb` 来模拟一个桌面环境。如果没有遇到验证码，它可以自动获得 cf_clearance。 

- 修改文件后缀 `config.json.example` 为 `config.json`

  根据文件内提示修改 `config.json` 配置文件

- 构建 Docker 镜像 `docker build -t chatgpt_telegram_bot .`

- 运行 Docker 容器  `docker run -d -v /config.json 所在路径/config.json:/ChatGPTBot/config.json chatgpt_telegram_bot`

   ### 如何停止机器人:

   * `docker ps` 查看正在运行的服务
   * `docker stop <BOT CONTAINER ID>` 来停止运行的机器人

## 命令列表

```
start - 开始
help - 使用帮助
rechat - 重置对话
addwhite - 添加白名单
```

## 感谢 [acheong08/ChatGPT](https://github.com/acheong08/ChatGPT) [anton By ChatGPT API](https://twitter.com/abacaj)
