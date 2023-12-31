import streamlit as st
from langchain.chains import ConversationChain
from langchain.chains.conversation.memory import ConversationBufferMemory
# TODO: Find a way to avoid token overflow and keep track of the conversation
from langchain.prompts.prompt import PromptTemplate
from langchain.llms import CTransformers, HuggingFaceTextGenInference
from langchain import OpenAI
from langchain.agents import create_pandas_dataframe_agent
from langchain.chains import SequentialChain
import pandas as pd
import consts
import os

_template = """O texto a seguir é uma conversa amigável em portugês (Brasil) entre um humano e uma assistente AI. 
Se a assistente AI não souber a resposta à pergunta, ela diz que não sabe. 
A assistente deve completar o texto respondendo uma única vez. 
A assistente não deve escrever o texto do humano. 
O sistema pode fazer questões e respondê-las, se o usuário já tiver respondido uma pergunta, a assistente AI deve responder de acordo com a resposta do usuário e não pelo sistema.

Conversa atual:

Pergunta do sistema: {system_question}
Resposta do sistema: {system_answer}
{history}
Humano: {input}

A próxima resposta da assistente AI é: """
_prompt = PromptTemplate(input_variables=["history", "input", "system_question", "system_answer"], template=_template)

messages_db = {}

llm = None
agent = None

def _get_llm(just_return_open_ai = False):
    if just_return_open_ai:
        return OpenAI(
            temperature=0.01,
            model_name=os.environ['OPENAI_LLM_MODEL_NAME']
        )
    global llm
    if llm is None:
        llm_type = os.environ['LLM_TYPE']

        if llm_type == consts.OPENAI_LLM_TYPE:
            llm = OpenAI(
                temperature=0.01,
                model_name=os.environ['OPENAI_LLM_MODEL_NAME']
            )
        elif llm_type == consts.LOCAL_LLAMA_LLM_TYPE:
            llm = CTransformers(
                model='models/llama-2-7b-chat.ggmlv3.q8_0.bin',
                model_type='llama',
                config={
                    'max_new_tokens': 1024,
                    'temperature': 0.01
                }
            )
        elif llm_type == consts.REMOTE_LLAMA_LLM_TYPE:
            llm = HuggingFaceTextGenInference(
                inference_server_url=os.environ['LLM_INSTANCE_URL'],
                temperature=0.01,
            )
            llm.client.headers = {"Authorization": f"Bearer {os.environ['HUGGINGFACEHUB_API_TOKEN']}"}
        else:
            raise Exception("Invalid LLM type")
    return llm

def _get_agent():
    global agent
    if agent is None:
        df = pd.read_excel('data/sp_data.xlsx')
        
        llm = _get_llm(just_return_open_ai=os.environ['USE_OPENAI_FOR_AGENT'].lower() == "true")
        
        agent = create_pandas_dataframe_agent(llm, df, verbose=True)
    return agent

def _get_history(messages):
    history = ''
    for i in range(len(messages)):
        if (i % 2) == 0:
            history += f"Humano: {messages[i]}"
        else:
            history += f"Assistente AI: {messages[i]}"
        if i < len(messages) - 1:
            history += '\n'
    return history

llm = _get_llm()
agent = _get_agent()

def get_response(user_input, chat_id):
    global messages_db
    if chat_id not in messages_db:
        messages_db[chat_id] = []
    
    prompt_instance = _prompt.format(
        input=user_input,
        history=_get_history(messages_db[chat_id]),
        system_question=user_input,
        system_answer=_get_agent().run(user_input),
    )
    
    response = _get_llm()(prompt_instance)

    messages_db[chat_id].append(user_input)
    messages_db[chat_id].append(response)

    print(prompt_instance)
    print(response)

    return response
