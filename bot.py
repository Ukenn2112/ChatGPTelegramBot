import asyncio
import json
import logging
import time

import openai
import redis
import telebot
from telebot.async_telebot import AsyncTeleBot
import aiohttp

telebot.logger.setLevel(logging.ERROR)
logging.getLogger().setLevel(logging.INFO)

logging.basicConfig(
    format='[%(levelname)s]%(asctime)s: %(message)s',
)

with open('config.json', "r") as f: config = json.load(f)
redis_pool = redis.Redis(host=config.get('redis_host'), port=config.get('redis_port'), db=config.get('redis_db'))
bot = AsyncTeleBot(config.get('bot_token'))
openai.api_key = config.get('api_key')

async def balance_check() -> bool:
    s = aiohttp.ClientSession(
        headers={"authorization": "Bearer " + config.get('api_key')},
    )
    async with s.get('https://api.openai.com/dashboard/billing/credit_grants') as resp:
        data = await resp.json()
        data = data['grants']['data'][0]
        if data['grant_amount'] - data['used_amount'] < config.get('balance_limit'):
            logging.warning('OpenAI API 余额到达预设阈值')
            return True
        else:
            return False

@bot.message_handler(commands=['start', 'help'], chat_types=['private'])
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
    chat_data = redis_pool.get(f"chatgpt:{message.from_user.id}")
    if not chat_data: return await bot.reply_to(message, '没有属于你的对话')
    redis_pool.delete(f"chatgpt:{message.from_user.id}")
    return await bot.reply_to(message, '已重置对话')

# 添加白名单
@bot.message_handler(commands=['addwhite'],
                     func=lambda m: m.from_user.id==config.get('admin_id'))
async def addwhite_message(message):
    if not message.reply_to_message:
        data = message.text.split(' ')
        if len(data) == 1:
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
@bot.message_handler(content_types=['text'], chat_types=['private'],
                     white_list=True)
async def echo_message_private(message):
    start_time = time.time()
    chat_data = redis_pool.get(f"chatgpt:{message.from_user.id}")
    if chat_data:
        messages: list = json.loads(chat_data)
        messages.append({"role": "user", "content": message.text})
    else:
        messages = [{"role": "user", "content": message.text}]
    from_user = f'{message.from_user.username or message.from_user.first_name or message.from_user.last_name}[{message.from_user.id}]'
    logging.info(f'{from_user}-->ChatGPT: {message.text}')
    if await balance_check():
        return await bot.reply_to(message, 'OpenAI API 余额预设阈值 停止使用')
    completion_resp = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=messages,
        frequency_penalty=1,
        presence_penalty=1,
    )
    back_message = completion_resp.choices[0].message
    end_time = time.time()
    elapsed_time = end_time - start_time
    logging.info(f"ChatGPT-->{from_user}: {back_message.content.encode('utf-8').decode()}" + '\n运行时间 {:.3f} 秒'.format(elapsed_time) + f'共消耗{completion_resp.usage.total_tokens}个令牌')
    messages.append(back_message)
    redis_pool.set(f"chatgpt:{message.from_user.id}", json.dumps(messages), ex=3600)
    try:
        return await bot.reply_to(message, back_message.content, parse_mode='Markdown')
    except:
        return await bot.reply_to(message, back_message.content)

# 群组
@bot.message_handler(content_types=['text'], chat_types=['supergroup'],
                     func=lambda m: m.text.startswith('ai '),
                     white_list=True)
async def echo_message_supergroup(message):
    start_time = time.time()
    chat_data = redis_pool.get(f"chatgpt:{message.from_user.id}")
    if chat_data:
        messages: list = json.loads(chat_data)
        messages.append({"role": "user", "content": message.text[3:]})
    else:
        messages = [{"role": "user", "content": message.text[3:]}]

    from_user = f'{message.from_user.username or message.from_user.first_name or message.from_user.last_name}[{message.from_user.id}]'
    logging.info(f'[Group] {from_user}-->ChatGPT: {message.text[3:]}')
    if await balance_check():
        return await bot.reply_to(message, 'OpenAI API 余额预设阈值 停止使用')
    completion_resp = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    back_message = completion_resp.choices[0].message
    end_time = time.time()
    elapsed_time = end_time - start_time
    logging.info(f"[Group] ChatGPT-->{from_user}: {back_message.content.encode('utf-8').decode()}" + '\n运行时间 {:.3f} 秒'.format(elapsed_time) + f'共消耗{completion_resp.usage.total_tokens}个令牌')
    messages.append(back_message)
    redis_pool.set(f"chatgpt:{message.from_user.id}", json.dumps(messages), ex=3600)
    try:
        return await bot.reply_to(message, back_message.content, parse_mode='Markdown')
    except:
        return await bot.reply_to(message, back_message.content)

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

if __name__ == '__main__':
    asyncio.run(bot.polling(non_stop=True, request_timeout=90))