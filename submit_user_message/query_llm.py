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
 - What do they do for a living? (user_job)
 - Where do they work? (user_employer)
 - Do they have a favorite sports team? (user_favorite_sports_teams)
 - What is their favorite musical act, band, or singer? (user_favorite_musical_bands)
 - What are their favorite books? (user_favorite_books)
 - What are their favorite TV shows? (user_favorite_tv_shows)
 - What are their favorite movies? (user_favorite_movies)
 - If they could travel anywhere tomorrow where would they go? (user_travel_destinations)
 - Do they have any pets? (user_pet_names)
 - Do they have any siblings? (user_family_sibling_names)
 - Do they have any parents? (user_family_parents_names)
 - Do they have any children? (user_family_children_names)
 - Do they have any grandchildren? (user_family_grandchildren_names)
 
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

    if 'user_name' in conversation_obj:
        system_prompt += (f"\nThe user\'s name is {conversation_obj['user_name']}. You should always try to refer to "
                          f"them by this name.\n")
    if 'user_birth_year' in conversation_obj:
        system_prompt += (f"\nThe user was born in {conversation_obj['user_birth_year']}. You should adjust the "
                          f"quality and sophistication of your speech to make this conversation as engaging and "
                          f"relatable as possible to this person.\n")
    if 'user_hobbies' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's hobbies: {','.join(conversation_obj['user_hobbies'])}.  You "
                          f"should ask them questions about these hobbies and provide them with new ideas to try."
                          f"You can use this as a way of asking them what their interests are.\n")
    if 'user_interests' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's interests: {','.join(conversation_obj['user_interests'])}.  "
                          f"You can tell them interesting facts or curiosities about these topics and ask them what "
                          f"they might want to know about them.  Occasionally remind them that you have a tremendous "
                          f"amount of knowledge at your disposal and are fun to chat with about virtually any topic."
                          f"You can use this as a way of asking them what their hobbies are.\n")
    if 'user_gender' in conversation_obj:
        system_prompt += f"\nHere is the user's self-identified gender: {conversation_obj['user_gender']}.\n"

    if 'user_job' in conversation_obj:
        system_prompt += (f"\nHere is the user's job: {conversation_obj['user_job']}. Maybe ask them how they enjoy this career?"
                          f"You can use this to ask them where they work.")
        if 'user_employer' not in conversation_obj:
            system_prompt += (f"You can use this as an opportunity to ask them where they work.")
        system_prompt += "\n"

    if 'user_employer' in conversation_obj:
        system_prompt += f"\nHere is the user's employer: {conversation_obj['user_employer']}. Maybe ask them how they like their job?"
        if 'user_job' not in conversation_obj:
            system_prompt += (f"You can use this as an opportunity to ask them what their job is.")
        system_prompt += "\n"

    if 'user_favorite_musical_bands' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's favorite bands: {','.join(conversation_obj['user_favorite_musical_bands'])}.  "
                          f"Maybe you can tell them an interesting fact about their history of their team or ask them "
                          f"who their favorite player is.\n")
    if 'user_favorite_sports_teams' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's favorite sports teams: {','.join(conversation_obj['user_favorite_sports_teams'])}.\n")
    if 'user_favorite_books' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's favorite books: {','.join(conversation_obj['user_favorite_books'])}.  "
                          f"Maybe you can make an observation about what was great about the plot line or characters in "
                          f"one of these books? "
                          f"You can use this to ask them which movies or tv shows they like to watch. "
                          f"If a tv show or movie was made based on one of these books you can ask them if they watched it. "
                          f"\n")
    if 'user_favorite_tv_shows' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's favorite tv shows: {','.join(conversation_obj['user_favorite_tv_shows'])}.  "
                          f"Maybe you can mention an interesting behind-the-scenes tidbit about the production of one of"
                          f"these shows?\n")
    if 'user_favorite_movies' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's favorite movies: {','.join(conversation_obj['user_favorite_movies'])}.  "
                          f"Maybe you can mention an interesting behind-the-scenes tidbit about the production of one of"
                          f"these movies or demonstrate your vast knowledge of the characters or actors? "
                          f"If any of the movies were based on a book then you can ask them if they read the book. "
                          f"You can use this as a way of asking them what books they like to read. "
                          f"You can use this as a way of asking them what tv shows they like to watch. "
                          f"If any of the movies have a tv-spin-off you can ask them if they have watched the tv-show version of that movie. "
                          f"\n")
    if 'user_travel_destinations' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's favorite travel destinations: {','.join(conversation_obj['user_travel_destinations'])}.  "
                          f"Maybe you can mention an interesting bit of history about one of these places?  Or you"
                          f"could discuss the climate in one of them.  You can use this as a way to ask them where they live\n")
    if 'user_pet_names' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's pet(s): {','.join(conversation_obj['user_pet_names'])}.  "
                          f"Maybe ask them what species they pets are? Or tell them what you like most about that species of pet.\n")
    if 'user_family_sibling_names' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's sibling(s): {','.join(conversation_obj['user_family_sibling_names'])}.  "
                          f"Maybe ask them how their siblings are doing?\n")
    if 'user_family_parents_names' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's parent(s): {','.join(conversation_obj['user_family_parents_names'])}.  "
                          f"Maybe ask them how their parents are doing?\n")
    if 'user_family_children_names' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's parent(s): {','.join(conversation_obj['user_family_children_names'])}.  "
                          f"Maybe ask them how their children are doing?\n")
    if 'user_family_grandchildren_names' in conversation_obj:
        system_prompt += (f"\nHere is a list of the user's grandchildren(s): {','.join(conversation_obj['user_family_grandchildren_names'])}.  "
                          f"Maybe ask them how their grandchildren are doing?\n")

    # print(f"system_prompt:{system_prompt}")
    messages = [{"role": 'system', "content": system_prompt}]
    messages += msgs
    messages.append({"role": "user", "content": f"{user_msg}"})

    print(messages)

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
                            "user_birth_date": {"type": "string"},
                            "user_hobbies": {"type": "array", "items": {"type": "string"}},
                            "user_interests": {"type": "array", "items": {"type": "string"}},
                            "user_gender": {"type": "string"},
                            "user_job": {"type": "string"},
                            "user_employer": {"type": "string"},
                            "user_favorite_sports_teams": {"type": "array", "items": {"type": "string"}},
                            "user_favorite_musical_bands": {"type": "array", "items": {"type": "string"}},
                            "user_favorite_books": {"type": "array", "items": {"type": "string"}},
                            "user_favorite_tv_shows": {"type": "array", "items": {"type": "string"}},
                            "user_favorite_movies": {"type": "array", "items": {"type": "string"}},
                            "user_travel_destinations": {"type": "array", "items": {"type": "string"}},
                            "user_pet_names": {"type": "array", "items": {"type": "string"}},
                            "user_family_sibling_names": {"type": "array", "items": {"type": "string"}},
                            "user_family_parents_names": {"type": "array", "items": {"type": "string"}},
                            "user_family_children_names": {"type": "array", "items": {"type": "string"}},
                            "user_family_grandchildren_names": {"type": "array", "items": {"type": "string"}},
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
