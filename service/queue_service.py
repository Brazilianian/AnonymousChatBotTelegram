import asyncio

from config.queue_config import *
from model.intimate_queue_model import IntimateQueueModel
from model.queue_user_model import QueueUserModel
from repo import queue_repo, user_repo, intimate_queue_repo
from service import bot_service
from states.chat_states import ChatStates


async def start_queue_worker():
    """
    Current method infinity checks for new connections for chatting
    It iterates through queue and match dialogs
    """
    while True:
        """INTIMATE"""
        queue_user_list: [IntimateQueueModel] = intimate_queue_repo.get_all_users()
        found = False
        for i in range(0, len(queue_user_list)):
            user_queue_i: IntimateQueueModel = queue_user_list[i]
            for j in range(i + 1, len(queue_user_list)):
                user_queue_j: IntimateQueueModel = queue_user_list[j]
                if ((user_queue_i.chat_id != user_queue_j.chat_id)
                        and
                        ((user_queue_i.sex_to_search == 'RANDOM'
                          or user_queue_i.sex_to_search == user_queue_j.sex)
                         and
                         (user_queue_j.sex_to_search == 'RANDOM'
                          or user_queue_j.sex_to_search == user_queue_i.sex))):
                    """ If match """
                    user_repo.update_user_connected_with(chat_id=user_queue_i.chat_id,
                                                         connected_with=user_queue_j.chat_id)

                    user_repo.update_user_connected_with(chat_id=user_queue_j.chat_id,
                                                         connected_with=user_queue_i.chat_id)

                    intimate_queue_repo.remove_user_from_queue(chat_id=user_queue_i.chat_id)
                    intimate_queue_repo.remove_user_from_queue(chat_id=user_queue_j.chat_id)
                    found = True

                    await bot_service.set_state(chat_id=user_queue_i.chat_id,
                                                user_id=user_queue_i.user_id,
                                                custom_state=ChatStates.chatting)

                    await bot_service.set_state(chat_id=user_queue_j.chat_id,
                                                user_id=user_queue_j.user_id,
                                                custom_state=ChatStates.chatting)

                    await bot_service.send_message_connected_with(chat_id=user_queue_i.chat_id)
                    await bot_service.send_message_connected_with(chat_id=user_queue_j.chat_id)
                    break
            if found:
                break

        """DEFAULT"""
        queue_user_list: [QueueUserModel] = queue_repo.get_all_users()
        found = False
        for i in range(0, len(queue_user_list)):
            user_queue_i: QueueUserModel = queue_user_list[i]
            for j in range(i + 1, len(queue_user_list)):
                user_queue_j: QueueUserModel = queue_user_list[j]
                if ((user_queue_i.chat_id != user_queue_j.chat_id)
                        and
                        ((user_queue_i.sex_to_search == 'RANDOM'
                          or user_queue_i.sex_to_search == user_queue_j.sex)
                         and
                         (user_queue_j.sex_to_search == 'RANDOM'
                          or user_queue_j.sex_to_search == user_queue_i.sex))):
                    """ If match """
                    user_repo.update_user_connected_with(chat_id=user_queue_i.chat_id,
                                                         connected_with=user_queue_j.chat_id)

                    user_repo.update_user_connected_with(chat_id=user_queue_j.chat_id,
                                                         connected_with=user_queue_i.chat_id)

                    queue_repo.remove_user_from_queue(chat_id=user_queue_i.chat_id)
                    queue_repo.remove_user_from_queue(chat_id=user_queue_j.chat_id)
                    found = True

                    await bot_service.set_state(chat_id=user_queue_i.chat_id,
                                                user_id=user_queue_i.user_id,
                                                custom_state=ChatStates.chatting)

                    await bot_service.set_state(chat_id=user_queue_j.chat_id,
                                                user_id=user_queue_j.user_id,
                                                custom_state=ChatStates.chatting)

                    await bot_service.send_message_connected_with(chat_id=user_queue_i.chat_id)
                    await bot_service.send_message_connected_with(chat_id=user_queue_j.chat_id)
                    break
            if found:
                break
        if not found:
            await asyncio.sleep(TIME_TO_SLEEP_FOR_QUEUE_SECONDS)
