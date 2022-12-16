# Author: @acheong08@fosstodon.org
# License: MIT
# Description: A Python wrapper for OpenAI's chatbot API
import json
import time
from typing import List

import httpx


class Debugger:
    def __init__(self, debug: bool = False):
        if debug:
            print("Debugger enabled on OpenAIAuth")
        self.debug = debug

    def set_debug(self, debug: bool):
        self.debug = debug

    def log(self, message: str, end: str = "\n"):
        if self.debug:
            print(message, end=end)


class AsyncChatbot:
    """
    Initialize the AsyncChatbot.

    :param session_token: The Session Token
    :type session_token: :obj:`str`

    :param conversation_id: The conversation ID
    :type conversation_id: :obj:`str`, optional

    :param parent_id: The parent ID
    :type parent_id: :obj:`str`, optional

    :param debug: Whether to enable debug mode
    :type debug: :obj:`bool`, optional

    :param refresh: Whether to refresh the session
    :type refresh: :obj:`bool`, optional

    :param request_timeout: The network request timeout seconds
    :type request_timeout: :obj:`int`, optional

    :param base_url: The base url to chat.openai.com backend server,
        useful when set up a reverse proxy to avoid network issue.
    :type base_url: :obj:`str`, optional

    :return: The Chatbot object
    :rtype: :obj:`Chatbot`
    """
    session_token: str
    conversation_id: str
    parent_id: str
    base_url: str
    conversation_id_prev_queue: List
    parent_id_prev_queue: List
    request_timeout: int

    def __init__(self, session_token: str, conversation_id=None, parent_id=None, debug=False, request_timeout=100,
                 base_url="https://justbrowse.io/api/chatgpt/", max_rollbacks=20):
        self.debugger = Debugger(debug)
        self.debug = debug
        self.session_token = session_token
        self.conversation_id = conversation_id
        self.parent_id = parent_id 
        self.base_url = base_url
        self.request_timeout = request_timeout
        self.max_rollbacks = max_rollbacks
        self.conversation_id_prev_queue = []
        self.parent_id_prev_queue = []
        self.get_uuid()

    async def __get_chat_text(self, data) -> dict:
        """
        Get the chat response as text -- Internal use only
        :param data: The data to send
        :type data: :obj:`dict`
        :return: The chat response
        :rtype: :obj:`dict`
        """
        # Create request session
        async with httpx.AsyncClient() as s:
            response = await s.post(
                self.base_url + "chat/" + self.uuid,
                json=data,
                timeout=self.request_timeout,
            )
            # Check if it is JSON
            try:
                response = json.loads(response.text)
                if response["status"] == "failed":
                    self.debugger.log("Incorrect response from ChatGPT API\n"+response["reason"])
                    raise Exception("Incorrect response from ChatGPT API")
                self.parent_id = response["parentId"]
                self.conversation_id = response["conversationId"]
                message = response["reply"][0]
                return {
                    "message": message,
                    "conversation_id": self.conversation_id,
                    "parent_id": self.parent_id,
                }
            except json.JSONDecodeError:
                self.debugger.log("Incorrect response from ChatGPT API\n"+response.text)
                raise Exception("Incorrect response from ChatGPT API")

    async def get_chat_response(self, prompt: str, output="text", conversation_id=None, parent_id=None) -> dict or None:
        """
        Get the chat response.

        :param prompt: The message sent to the chatbot
        :type prompt: :obj:`str`

        :param output: The output type `text` or `stream`
        :type output: :obj:`str`, optional

        :return: The chat response `{"message": "Returned messages", "conversation_id": "conversation ID", "parent_id": "parent ID"}` or None
        :rtype: :obj:`dict` or :obj:`None`
        """
        self.uuid_startus()
        data = {
            "message": prompt,
            "conversationId": conversation_id or self.conversation_id,
            "parentId": parent_id or self.parent_id
        }
        self.conversation_id_prev_queue.append(data["conversationId"])  # for rollback
        self.parent_id_prev_queue.append(data["parentId"])
        while len(self.conversation_id_prev_queue) > self.max_rollbacks:  # LRU, remove oldest
            self.conversation_id_prev_queue.pop(0)
        while len(self.parent_id_prev_queue) > self.max_rollbacks:
            self.parent_id_prev_queue.pop(0)
        if output == "text":
            return await self.__get_chat_text(data)
        else:
            raise ValueError("Output must be either 'text'")

    def rollback_conversation(self, num=1) -> None:
        """
        Rollback the conversation.
        :param num: The number of messages to rollback
        :return: None
        """
        for i in range(num):
            self.conversation_id = self.conversation_id_prev_queue.pop()
            self.parent_id = self.parent_id_prev_queue.pop()

    def uuid_startus(self) -> None:
        """
        Get the uuid status

        :return: None
        """
        if self.uuid:
            s = httpx.Client()
            while True:
                response = s.get(
                    self.base_url + "status?id=" + self.uuid,
                ).json()
                if response["status"] == "ready":
                    return
                elif response["status"] == "failed":
                    self.debugger.log("Failed to get uuid \n" + response["reason"])
                    self.get_uuid()
                    return self.uuid_startus()
                self.debugger.log("Waiting for uuid to be ready")
                time.sleep(3)
        else:
            self.debugger.log("No uuid provided")
            raise ValueError("No uuid provided")
    
    def get_uuid(self) -> None:
        """
        Get the uuid

        :return: None
        """
        if self.session_token:
            response = httpx.get(
                self.base_url + "connect?sessionToken=" + self.session_token
                )
            if response.status_code == 429:
                self.debugger.log("Too many requests")
                raise ValueError("Too many requests")
            elif response.status_code == 200:
                self.uuid = response.json()["id"]
                return
            else:
                self.debugger.log("Incorrect response from ChatGPT API")
                raise ValueError("Incorrect response from ChatGPT API")
        else:
            self.debugger.log("No session token provided")
            raise ValueError("No session token provided")