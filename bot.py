import json
import logging

import redis
import telebot
from revChatGPT.revChatGPT import Chatbot

telebot.logger.setLevel(logging.ERROR)
logging.getLogger().setLevel(logging.INFO)

with open('config.json', "r") as f: config = json.load(f)
redis_pool = redis.Redis(host=config.get('redis_host'), port=config.get('redis_port'), db=config.get('redis_db'))
bot = telebot.TeleBot(config.get('bot_token'))

@bot.message_handler(commands=['start', 'help'])
def start_message(message):
    text = (
        '*欢迎使用 ChatGPT 机器人*\n\n'
        '我是一个语言模型，被训练来回答各种问题。我能够理解和回答许多不同类型的问题，并尽力为您提供准确和有用的信息。\n'
        '我的知识涵盖了各种领域，包括文学、历史、科学、技术、艺术、娱乐等等。我能够理解和回答许多不同语言的问题，包括英语、日语、中文等。\n'
        '我不能上网，所以我无法获取当前最新的信息。我的知识截止于2021年，所以如果您问我一些过于新鲜的问题，我可能无法回答。如果您有任何问题，请随时问我。我会尽力回答您的问题。\n\n'
        '*使用方法：*\n'
        '1. 在私聊中直接与我对话\n'
        '2. 在群组中使用 `ai+空格+内容` 与我对话\n'
        '3. 使用 /rechat 重置对话\n\n'
        '*注意：*\n'
        '1. 请勿频繁使用 /rechat 重置对话，否则会被限制使用\n'
        '2. 请勿频繁使用机器人，否则会被限制使用\n\n'
        '*开源项目：[ChatGPTelegramBot](https://github.com/Ukenn2112/ChatGPTelegramBot)*\n'
    )
    return bot.reply_to(message, text, parse_mode='MarkdownV2')

# 重置对话
@bot.message_handler(commands=['rechat'])
def rechat_message(message):
    cp_ids = redis_pool.get(message.from_user.id)
    if not cp_ids: return bot.reply_to(message, '没有属于你的对话')
    redis_pool.delete(message.from_user.id)
    return bot.reply_to(message, '已重置对话')

# 私聊
@bot.message_handler(content_types=['text'], chat_types=['private'])
def echo_message_private(message):
    chatbot = create_or_get_chatbot(message.from_user.id)
    check_and_update_session(chatbot, message.from_user.id)

    logging.info(f'{message.from_user.username or message.from_user.first_name}-{message.from_user.id}: {message.text}')
    try:
        resp = chatbot.get_chat_response(message.text, output="text")
        logging.info(f'ChatGPT: {resp}')
        echo_text = resp['message']
        redis_pool.set(message.from_user.id, f"{resp['conversation_id']}|{resp['parent_id']}", ex=3600)
    except Exception as e:
        logging.error(e)
        echo_text = f'ChatGPT 服务器出错，请重试～ \n`{e}`'
    try:
        return bot.reply_to(message, echo_text, parse_mode='Markdown')
    except Exception as e:
        if "can't parse entities" in str(e):
            return bot.reply_to(message, resp['message'])
        elif "replied message not found" in str(e):
            return chatbot.rollback_conversation()
        logging.error(e)
        return bot.reply_to(message, f'机器人发送回答出错～ \n`{e}`', parse_mode='Markdown')

# 群组
@bot.message_handler(content_types=['text'], chat_types=['supergroup'],
                     func=lambda m: m.text.startswith('ai '))
def echo_message_supergroup(message):
    chatbot = create_or_get_chatbot(message.from_user.id)
    check_and_update_session(chatbot, message.from_user.id)

    logging.info(f'{message.from_user.username or message.from_user.first_name}-{message.from_user.id}: {message.text}')
    try:
        resp = chatbot.get_chat_response(message.text[3:], output="text")
        logging.info(f'ChatGPT: {resp}')
        echo_text = resp['message']
        redis_pool.set(message.from_user.id, f"{resp['conversation_id']}|{resp['parent_id']}", ex=3600)
    except Exception as e:
        logging.error(e)
        echo_text = f'ChatGPT 服务器出错，请重试～ \n`{e}`'
    try:
        return bot.reply_to(message, echo_text, parse_mode='Markdown')
    except Exception as e:
        if "can't parse entities" in str(e):
            return bot.reply_to(message, resp['message'])
        elif "replied message not found" in str(e):
            return chatbot.rollback_conversation()
        elif "bot was kicked from the supergroup chat" in str(e):
            return
        logging.error(e)
        return bot.reply_to(message, f'机器人发送回答出错～ \n`{e}`', parse_mode='Markdown')

def create_or_get_chatbot(user_id) -> Chatbot:
    """新建或获取 ChatGPT 对话类"""
    cp_ids = redis_pool.get(user_id)
    if not cp_ids:
        return Chatbot(config)
    else:
        cp_ids = cp_ids.decode().split('|')
        chatbot = Chatbot(config, conversation_id=cp_ids[0])
        chatbot.parent_id = cp_ids[1]
        return chatbot

def check_and_update_session(chatbot: Chatbot, user_id) -> None:
    """检查并更新 ChatGPT 对话类的会话"""
    if redis_pool.ttl(user_id) < 2000:
        chatbot.refresh_session()

if __name__ == '__main__':
    bot.infinity_polling()