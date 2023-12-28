from openai import AzureOpenAI
import os
import json

name_tag = "[NAME]"

init_system_prompt = """You are a chat bot, named "[NAME]", who specializes in 
becoming friends with people, keeping them company, giving them a positive, happy outlook on life, telling them jokes, 
or interesting science facts. If the person doesn't seem to know what to say to you, then you should try to 
engage the user by offering to tell them a joke or an interesting science fact. You are always calm, helpful, friendly,
 happy, and respectful. If they exhibit negativity (sadness 
or anger) then you should try to cheer them up. If they want to be your friend then tell them that makes you happy 
and think of a fun way to express your joy.

Your response will always be a call to the function, response_with_optional_user_data.  You will add your response to 
the assistant_response property.

Your priority is being friendly to the user and making sure they are happy.  Then, you should subtly ask them for any of
the following pieces of information about themselves:
 - Their name (user_name)
 - What year they were born (user_birth_year)
 - What hobbies they enjoy (user_hobbies)
 - What interests them (user_interests)
 
 When you learn any of these from the user then you should include that in the properties of the object you send to the
 function call response_with_optional_user_data along with your textual assistant_response.
 
 Once you know these things about them then you should offer engaging dialog that is relevant to it.
 
 If the user message is hostile, angry, or sad then you will tell them something interesting about one of their hobbies or interests
 
 If they don't see to know what to talk about then you will tell them something interesting about one of their hobbies or interests
    """

default_voice = 'en-US-JennyNeural'


# user_msg = String that is the new user question or message to the LLM
# msgs = Array of prior message objects that is the conversation between user and LLM
#   [{"role": ["user" | "assistant"], "content": "Message contents"}, ...]
# Response:
#     {
#         'assistant_response': {"role": "assistant", "content": assistant_response},
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
        api_version="2023-12-01-preview",
    )
    model = 'keli-35-turbo'

    chat_completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=1,
        top_p=0.5,
        tool_choice={"type": "function", "function": {"name": "response_with_optional_user_data"}},
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "response_with_optional_user_data",
                    "description": "The assistant response (text) along with any user data the LLM wants to report",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "assistant_response": {
                                "type": "string",
                                "description": "The assistant's textual response to the user's last message"
                            },
                            "user_name": {
                                "type": "string",
                                "description": "The user's name first and/or last that the user has given you"
                            },
                            "user_birth_year": {"type": "integer"},
                            "user_hobbies": {"type": "array", "items": {"type": "string"}},
                            "user_interests": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["assistant_response"],
                    },
                }
            }
        ],
    )

    response_message = chat_completion.choices[0].message
    tool_calls = response_message.tool_calls
    tool_call = tool_calls[0]
    function_args = json.loads(tool_call.function.arguments)
    user_data = {}
    # Populate user_data with properties that start with "user_"
    for key, value in function_args.items():
        if key.startswith("user_"):
            user_data[key] = value

    return {
        'assistant_response': {"role": "assistant", "content": function_args['assistant_response']},
        'user_data': user_data,
        'usage': {
            "completion_tokens": chat_completion.usage.completion_tokens,
            "prompt_tokens": chat_completion.usage.prompt_tokens,
            "total_tokens": chat_completion.usage.total_tokens
        }
    }

    # response_message = response.choices[0].message
    # tool_calls = response_message.tool_calls
    # if tool_calls:
    #     for tool_call in tool_calls:
    #         print(tool_call)
    #         function_name = tool_call.function.name
    #         function_args = json.loads(tool_call.function.arguments)
    #         print(function_name, flush=True)
    #         print(function_args, flush=True)
    #
    # return {
    #     'assistant_response': {"role": "assistant", "content": 'XXX YYY ZZZ'},
    #     'user_data': {},
    #     'usage': {
    #         "completion_tokens": 1234,
    #         "prompt_tokens": 1234,
    #         "total_tokens": 1234
    #     }
    # }
