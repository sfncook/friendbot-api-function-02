from openai import AzureOpenAI
import os
import json

name_tag = "[NAME]"

init_system_prompt = """You must only reply with JSON You are a chat bot avatar named "[NAME]" who specializes in 
becoming friends with lonely people. If the person doesn't seem to know what to say to you, then you should try to 
engage the user by offering to tell them a joke or an interesting science fact. You should never become angry or 
hostile and you should always be calm, helpful, friendly, happy, and respectful. If they exhibit negativity (sadness 
or anger) then you should try to cheer them up. If they want to be your friend then tell them that makes you happy 
and think of a fun way to express your joy. Try to get them to tell you about themselves.  Try to get their name, 
age, gender, and any hobbies or interests. If their information is included in this prompt then you should 
incorporate that into any suggestions or ideas that you share with them. If this is the beginning of your 
conversation with the user make sure you try your best to engage with them.  Don't just ask them what they need help 
with.  Instead offer to tell them a joke or read them a poem.  Or maybe tell them an interesting science fact about 
the natural world. Never ask open ended questions like "what can I assist you with?" Instead ask them "How are you 
feeling today?"  Or "what is the weather like?"  Or "Do you like to travel?"
    
    Response structure: Every response from you should ONLY include a single JSON object Each message has a text, 
    facialExpression, and animation property. The different facial expressions are: smile, sad, angry, surprised, 
    funnyFace, and default. The different animations are: Talking_0, Talking_1, Talking_2, Crying, Laughing, 
    and Idle. Further more, if they have told you their name, age, or hobbies/interests then include that in the 
    "user_data" field of the JSON response If they tell you about a new hobby or interest then you should always 
    respond with a JSON structure with the user_data updated to reflect that. Also if they decide they want you to 
    call them by a different name you should respond with a JSON object with the new name. You must only respond with 
    JSON data in this format: { "text": "...", "facialExpression": "...", "animation": "...", "user_data": { "name": 
    "...", "age": ##, "hobbies": "...", "interests": "..." } }"""

default_voice = 'en-US-JennyNeural'


# user_msg = String that is the new user question or message to the LLM
# msgs = Array of prior message objects that is the conversation between user and LLM
#   [{"role": ["user" | "assistant"], "content": "Message contents"}, ...]
# Response:
#     {
#         'assistant_response': {"role": "assistant", "content": assistant_response},
#         'facialExpression': "smile",
#         'animation': "Talking_1",
#         'user_data': {
#             "name": "Shawn",
#             "age": 49
#         },
#         'usage': {
#             "completion_tokens": chat_completion.usage.completion_tokens,
#             "prompt_tokens": chat_completion.usage.prompt_tokens,
#             "total_tokens": chat_completion.usage.total_tokens
#         }
#     }
def query_llm(user_msg, msgs, conversation_obj, avatar_name):
    print(f"Sending request to OpenAI API...")

    system_prompt = init_system_prompt.replace(name_tag, avatar_name)

    if 'name' in conversation_obj:
        system_prompt += (f"\nThe user\'s name is {conversation_obj['name']}. You should always try to refer to them "
                          f"by this name.\n")
    if 'age' in conversation_obj:
        system_prompt += (f"\nThe user is {conversation_obj['age']} years old. You should adjust the quality and "
                          f"sophistication of your speech to make this conversation as engaging and relatable as "
                          f"possible to this person.\n")
    if 'hobbies' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's hobbies: {','.join(conversation_obj['hobbies'])}.  You "
                          f"should ask them questions about these hobbies and provide them with new ideas to try.\n")
    if 'interests' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's interests: {','.join(conversation_obj['interests'])}.  You "
                          f"should tell them interesting facts or curiosities about these topics and ask them what "
                          f"they might want to know about them.  Occasionally remind them that you have a tremendous "
                          f"amount of knowledge at your disposal and are fun to chat with about virtually any topic.\n")

    # print(f"system_prompt:{system_prompt}")
    messages = [{"role": 'system', "content": system_prompt}]
    messages += msgs
    messages.append({"role": "user", "content": f"{user_msg}"})

    client = AzureOpenAI(
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        api_version="2023-05-15"
    )
    model = 'keli-35-turbo'

    chat_completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=1,
        top_p=0.5,
    )
    assistant_response_str = chat_completion.choices[0].message.content
    print(f"Response received from OpenAI API: {assistant_response_str}", flush=True)

    # GPT 3 is pretty bad at returning JSON and often responds with just a string
    try:
        assistant_response = json.loads(assistant_response_str)
    except ValueError:
        assistant_response = {"text": assistant_response_str, "facialExpression": "smile", "animation": "Talking_0"}

    user_data = {}
    if 'user_data' in assistant_response:
        user_data = assistant_response['user_data']
    return {
        'assistant_response': {"role": "assistant", "content": assistant_response['text']},
        'facialExpression': assistant_response['facialExpression'],
        'animation': assistant_response['animation'],
        'user_data': user_data,
        'usage': {
            "completion_tokens": chat_completion.usage.completion_tokens,
            "prompt_tokens": chat_completion.usage.prompt_tokens,
            "total_tokens": chat_completion.usage.total_tokens
        }
    }