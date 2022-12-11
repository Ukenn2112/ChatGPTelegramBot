import asyncio
import json
import logging
import time

import redis
import telebot
from revChatGPT.revChatGPT import Chatbot
from telebot.async_telebot import AsyncTeleBot

telebot.logger.setLevel(logging.ERROR)
logging.getLogger().setLevel(logging.INFO)

logging.basicConfig(
    format='[%(levelname)s]%(asctime)s: %(message)s',
)

with open('config.json', "r") as f: config = json.load(f)
redis_pool = redis.Redis(host=config.get('redis_host'), port=config.get('redis_port'), db=config.get('redis_db'))
bot = AsyncTeleBot(config.get('bot_token'))

@bot.message_handler(commands=['start', 'help'])
async def start_message(message):
    text = (
        '*欢迎使用 ChatGPT 机器人*\n\n'
        '我是一个语言模型，被训练来回答各种问题。我能够理解和回答许多不同类型的问题，并尽力为您提供准确和有用的信息。\n'
        '我的知识涵盖了各种领域，包括文学、历史、科学、技术、艺术、娱乐等等。我能够理解和回答许多不同语言的问题，包括英语、日语、中文等。\n'
        '我不能上网，所以我无法获取当前最新的信息。我的知识截止于2021年，所以如果您问我一些过于新鲜的问题，我可能无法回答。如果您有任何问题，请随时问我。我会尽力回答您的问题。\n\n'
        '*使用方法：*\n'
        '1\\. 在私聊中直接与我对话\n'
        '2\\. 在群组中使用 `ai\\+空格\\+内容` 与我对话\n'
        '3\\. 使用 \\/rechat 重置对话\n\n'
        '*注意：*\n'
        '1\\. 请勿频繁使用 \\/rechat 重置对话，否则会被限制使用\n'
        '2\\. 请勿频繁使用机器人，否则会被限制使用\n\n'
        '*开源项目：[ChatGPTelegramBot](https://github.com/Ukenn2112/ChatGPTelegramBot)*\n'
    )
    return await bot.reply_to(message, text, parse_mode='MarkdownV2')

# 重置对话
@bot.message_handler(commands=['rechat'])
async def rechat_message(message):
    cp_ids = redis_pool.get(message.from_user.id)
    if not cp_ids: return await bot.reply_to(message, '没有属于你的对话')
    redis_pool.delete(message.from_user.id)
    return await bot.reply_to(message, '已重置对话')

# 添加白名单
@bot.message_handler(commands=['addwhite'],
                     func=lambda m: m.from_user.id==config.get('admin_id'))
async def addwhite_message(message):
    if not message.reply_to_message:
        data = message.text.split(' ')
        if len(data) == 1:
            return await bot.reply_to(message, '输入的对话 ID 不正确')
        elif not data[1].isdigit():
            return await bot.reply_to(message, '请回复需要加入白名单的用户消息，或者直接输入对话 ID')
        add_white_id = int(data[1])
    else:
        add_white_id = message.reply_to_message.from_user.id
    if add_white_id in config.get('white_list'):
        return await bot.reply_to(message, '该对话 ID 已经在白名单中了')
    config['white_list'].append(add_white_id)
    with open('config.json', "w") as f: json.dump(config, f, indent=4)
    return await bot.reply_to(message, '已添加到白名单')

# 私聊
@bot.message_handler(content_types=['text'], chat_types=['private'])
async def echo_message_private(message):
    start_time = time.time()
    chatbot = create_or_get_chatbot(message.from_user.id)
    check_and_update_session(chatbot, message.from_user.id)

    from_user = f'{message.from_user.username or message.from_user.first_name or message.from_user.last_name}[{message.from_user.id}]'
    logging.info(f'{from_user}-->ChatGPT: {message.text}')
    try:
        resp = chatbot.get_chat_response(message.text, output="text")
        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.info(f"ChatGPT-->{from_user}: {resp['message']}" + '\n运行时间 {:.3f} 秒'.format(elapsed_time))
        redis_pool.set(message.from_user.id, f"{resp['conversation_id']}|{resp['parent_id']}", ex=3600)
    except Exception as error:
        logging.error(error)
        return await bot.reply_to(message, f'ChatGPT 服务器出错，请重试～ \n`{error}`', parse_mode='Markdown')

    try:
        return await bot.reply_to(message, resp['message'], parse_mode='Markdown')
    except Exception as error:
        if "can't parse entities" in str(error):
            return await bot.reply_to(message, resp['message'])
        elif "replied message not found" in str(error):
            return chatbot.rollback_conversation()
        logging.error(error)
        return await bot.reply_to(message, f'机器人发送回答出错～ \n`{error}`', parse_mode='Markdown')

# 群组
@bot.message_handler(content_types=['text'], chat_types=['supergroup'],
                     func=lambda m: m.text.startswith('ai '),
                     white_list=True)
async def echo_message_supergroup(message):
    start_time = time.time()
    chatbot = create_or_get_chatbot(message.from_user.id)
    check_and_update_session(chatbot, message.from_user.id)

    from_user = f'{message.from_user.username or message.from_user.first_name or message.from_user.last_name}[{message.from_user.id}]'
    logging.info(f'{from_user}-->ChatGPT: {message.text[3:]}')
    try:
        resp = chatbot.get_chat_response(message.text[3:], output="text")
        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.info(f"ChatGPT-->{from_user}: {resp['message']}" + '\n运行时间 {:.3f} 秒'.format(elapsed_time))
        redis_pool.set(message.from_user.id, f"{resp['conversation_id']}|{resp['parent_id']}", ex=3600)
    except Exception as error:
        logging.error(error)
        return await bot.reply_to(message, f'ChatGPT 服务器出错，请重试～ \n`{error}`', parse_mode='Markdown')

    try:
        return await bot.reply_to(message, resp['message'], parse_mode='Markdown')
    except Exception as error:
        if "can't parse entities" in str(error):
            return await bot.reply_to(message, resp['message'])
        elif "replied message not found" in str(error):
            return chatbot.rollback_conversation()
        elif "bot was kicked from the supergroup chat" in str(error):
            return
        logging.error(error)
        return await bot.reply_to(message, f'机器人发送回答出错～ \n`{error}`', parse_mode='Markdown')

class WhiteList(telebot.asyncio_filters.SimpleCustomFilter):
    """白名单过滤器"""
    key='white_list'
    @staticmethod
    async def check(message: telebot.types.Message):
        if not config.get('white_list'): return True
        elif message.chat.id in config.get('white_list'):
            return True
        else:
            await bot.reply_to(message, ('*由于 ChatGPT API 性能的限制，该机器人现已开启白名单对话限制\n'
                                         '由于该对话或群组不在白名单中，无法使用此机器人～\n'
                                         '如果您想继续使用请尝试自建机器人～\n'
                                         'Github\\: [ChatGPTelegramBot](https://github.com/Ukenn2112/ChatGPTelegramBot)*'), parse_mode='MarkdownV2')
            return False
bot.add_custom_filter(WhiteList())

def create_or_get_chatbot(user_id) -> Chatbot:
    """新建或获取 ChatGPT 对话类"""
    cp_ids = redis_pool.get(user_id)
    if not cp_ids:
        return Chatbot(config)
    else:
        cp_ids = cp_ids.decode().split('|')
        chatbot = Chatbot(
            config,
            conversation_id=cp_ids[0],
            parent_id=cp_ids[1]
            )
        return chatbot

def check_and_update_session(chatbot: Chatbot, user_id) -> None:
    """检查并更新 ChatGPT 对话类的会话"""
    if redis_pool.ttl(user_id) < 2000:
        chatbot.refresh_session()
        redis_pool.set(user_id, f"{chatbot.conversation_id}|{chatbot.parent_id}", ex=3600)

if __name__ == '__main__':
    asyncio.run(bot.infinity_polling())