from datetime import datetime, timezone, timedelta
import copy
import time
import json
import pathlib
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter, Retry

MAX_TEXT_LENGTH = 2000
COMPLETION_MARK = "⚐"

INLINE_TYPES = (
    "heading_1",
    "heading_2",
    "heading_3",
)
RICH_TEXT_TYPES = (
    "heading_1",
    "heading_2",
    "heading_3",
    "paragraph",
    "bulleted_list_item",
    "numbered_list_item",
    "toggle",
    "to_do",
    "quote",
    "callout",
)
ALLOWED_HTTP_METHODS = (
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "PATCH",
)


class TranslatorClient:
    def __init__(self, google_cloud_api_key: str):
        self.default_headers = {
            "Content-type": "application/json",
        }

        self.session = requests.Session()
        self.session.headers.update(self.default_headers)
        retry = Retry(
            total=20,
            backoff_factor=1,
            status_forcelist=[429],
            allowed_methods=ALLOWED_HTTP_METHODS,
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

        self.google_cloud_api_key = google_cloud_api_key

    def translate(
        self,
        text: str,
        source_language: Optional[str],
        target_language: Optional[str],
    ):
        url = "https://translation.googleapis.com/language/translate/v2"

        # Specify Query Parameters
        params = {
            "format": "text",
            "model": "base",
            "key": self.google_cloud_api_key,
        }

        body = {
            "q": [text],
            "source": source_language,
            "target": target_language,
        }

        # Send the request and get response
        raw_response = self.session.post(url, params=params, json=body)
        try:
            response = raw_response.json()
        except Exception:
            print(raw_response.request.headers)
            print(text)
            print(raw_response._content)
            raise ConnectionError

        if raw_response.status_code != 200:
            print(f"HTTP {raw_response.status_code}: {response['error']['details']}\n")

        translation = response["data"]["translations"][0]["translatedText"]
        print(f"{text}\n")
        print(f"{translation}\n")

        # Return the translation
        return translation


class NotionClient:
    def __init__(self, notion_api_key: str):
        self.default_headers = {
            "Authorization": f"Bearer {notion_api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        self.session = requests.Session()
        self.session.headers.update(self.default_headers)
        retry = Retry(
            total=20,
            backoff_factor=1,
            status_forcelist=[429],
            allowed_methods=ALLOWED_HTTP_METHODS,
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get_property(self, page_id: str, property_id: str):
        url = f"https://api.notion.com/v1/pages/{page_id}/properties/{property_id}"
        raw_response = self.session.get(url)
        response = raw_response.json()
        if raw_response.status_code != 200:
            print(f"HTTP {raw_response.status_code}: {response['message']}\n")
        return response

    def get_title_text(self, page_id: str):
        title_property = self.get_property(page_id, "title")["results"][0]
        return title_property["title"]["plain_text"]

    def get_some_blocks(
        self,
        block_id: str,
        start_cursor: Optional[str] = None,
        page_size: Optional[str] = None,
    ):
        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        params: dict[str, str] = {}
        if start_cursor is not None:
            params["start_cursor"] = start_cursor
        if page_size is not None:
            params["page_size"] = page_size
        raw_response = self.session.get(url, params=params)
        response = raw_response.json()
        if raw_response.status_code != 200:
            print(f"HTTP {raw_response.status_code}: {response['message']}\n")
        return response

    def get_blocks(self, block_id: str, include_subpages: bool) -> list[Any]:
        blocks_response = self.get_some_blocks(block_id)
        blocks = blocks_response.get("results")
        if blocks is None:
            return []
        while blocks_response.get("has_more"):
            blocks_response = self.get_some_blocks(
                block_id, blocks_response.get("next_cursor")
            )
            blocks.extend(blocks_response.get("results"))
        for block in blocks:
            if block["type"] == "child_page":
                if include_subpages:
                    blocks.extend(self.get_blocks(block["id"], include_subpages))
        print(f"Found {len(blocks)} blocks\n")
        return blocks

    def get_text(self, rich_text_object: dict[str, Any]):
        # Concatenates a rich text array into plain text
        text = ""
        for rt in rich_text_object["rich_text"]:
            text += rt["plain_text"]
        return text

    def get_block_text(self, block: dict[str, Any]):
        if block["type"] in RICH_TEXT_TYPES:
            return self.get_text(block[block["type"]])
        else:
            return ""

    def update_block(self, block_id: str, payload: dict[str, Any]):
        url = f"https://api.notion.com/v1/blocks/{block_id}"
        raw_response = self.session.patch(url, json=payload)
        response = raw_response.json()
        if raw_response.status_code != 200:
            print(f"HTTP {raw_response.status_code}: {response['message']}\n")

    def delete_block(self, block_id: str):
        url = f"https://api.notion.com/v1/blocks/{block_id}"
        raw_response = self.session.delete(url)
        response = raw_response.json()
        if raw_response.status_code != 200:
            print(f"HTTP {raw_response.status_code}: {response['message']}\n")

    def append_block_children(self, block_id: str, payload: dict[str, Any]):
        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        raw_response = self.session.patch(url, json=payload)
        response = raw_response.json()
        if raw_response.status_code != 200:
            print(f"HTTP {raw_response.status_code}: {response['message']}\n")

    def update_title(self, page_id: str, title: str):
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            }
        }
        raw_response = self.session.patch(url, json=payload)
        response = raw_response.json()
        if raw_response.status_code != 200:
            print(f"HTTP {raw_response.status_code}: {response['message']}\n")


class Converter:
    def __init__(
        self,
        source_language: Optional[str],
        target_language: Optional[str],
        google_cloud_api_key: str,
        notion_api_key: str,
    ):
        self.notion_client = NotionClient(notion_api_key)
        self.translate_client = TranslatorClient(google_cloud_api_key)
        self.source_language = source_language
        self.target_language = target_language

    def handle_page_block(self, page_id: str, create_translation: bool):
        source_text = self.notion_client.get_title_text(page_id)
        source_text = source_text.strip()
        division_text = f" {COMPLETION_MARK} "

        if create_translation:
            if COMPLETION_MARK in source_text:
                return source_text

            converted_text = self.translate_client.translate(
                source_text,
                self.source_language,
                self.target_language,
            )
            converted_text = f"{converted_text}{division_text}{source_text}"

            self.notion_client.update_title(page_id, converted_text)

        else:
            if COMPLETION_MARK in source_text:
                converted_text = source_text.split(COMPLETION_MARK)[1].strip()
                self.notion_client.update_title(page_id, converted_text)

    def handle_normal_block(
        self,
        block: dict[str, Any],
        realtime: bool,
        create_translation: bool,
    ):
        if realtime:
            time_format = "%Y-%m-%dT%H:%M:%S.000Z"
            last_edited_time = datetime.strptime(block["last_edited_time"], time_format)
            last_edited_time = last_edited_time.replace(tzinfo=timezone.utc)
            if last_edited_time + timedelta(minutes=5) < datetime.now(timezone.utc):
                return

        source_text = self.notion_client.get_block_text(block)
        source_text = source_text.strip()

        if source_text == "":
            return

        if block["type"] in INLINE_TYPES:
            if create_translation:
                if COMPLETION_MARK in source_text:
                    return
                mark_text = f" {COMPLETION_MARK} "
                translated = self.translate_client.translate(
                    source_text,
                    self.source_language,
                    self.target_language,
                )
                block[block["type"]]["rich_text"] += [
                    {
                        "type": "text",
                        "text": {"content": mark_text},
                    },
                    {
                        "type": "text",
                        "text": {"content": translated},
                    },
                ]
                self.notion_client.update_block(block["id"], block)
            else:
                if COMPLETION_MARK in source_text:
                    for turn, item in enumerate(block[block["type"]]["rich_text"]):
                        if COMPLETION_MARK in item["text"]["content"]:
                            originals = block[block["type"]]["rich_text"]
                            block[block["type"]]["rich_text"] = originals[:turn]
                    self.notion_client.update_block(block["id"], block)

        else:
            mark_text = f" {COMPLETION_MARK} {len(source_text):04}"

            before_translation_child = None
            before_source_text_length = 0
            children = self.notion_client.get_blocks(block["id"], False)

            if create_translation:
                for child in children:
                    child_text = self.notion_client.get_block_text(child)
                    if COMPLETION_MARK in child_text:
                        if before_translation_child is None:
                            before_translation_child = child
                            splitted_texts = child_text.split(COMPLETION_MARK)
                            before_source_text_length = int(splitted_texts[-1].strip())
                        else:
                            self.notion_client.delete_block(child["id"])

                if before_translation_child is not None:
                    if len(source_text) == before_source_text_length:
                        return

                if before_translation_child is not None:
                    new_translation_child = before_translation_child
                else:
                    new_translation_child = copy.deepcopy(block)

                translated = self.translate_client.translate(
                    source_text,
                    self.source_language,
                    self.target_language,
                )
                maximum_content_length = MAX_TEXT_LENGTH - len(mark_text)
                if len(translated) > maximum_content_length:
                    translated = translated[:maximum_content_length]
                final_text = translated + mark_text
                new_translation_child[new_translation_child["type"]]["rich_text"] = [
                    {
                        "type": "text",
                        "text": {"content": final_text},
                    },
                ]

                if before_translation_child is not None:
                    payload = new_translation_child
                    self.notion_client.update_block(
                        before_translation_child["id"], payload
                    )
                else:
                    payload = {"children": [new_translation_child]}
                    self.notion_client.append_block_children(block["id"], payload)
            else:
                for child in children:
                    child_text = self.notion_client.get_block_text(child)
                    if COMPLETION_MARK in child_text:
                        print(f"{child_text}\n")
                        self.notion_client.delete_block(child["id"])

    def convert_page(
        self,
        page_id: str,
        include_subpages: bool,
        realtime: bool,
        create_translation: bool,
    ):
        task_start_time = datetime.now(timezone.utc)

        page_blocks = self.notion_client.get_blocks(page_id, include_subpages)

        self.handle_page_block(page_id, create_translation)

        for block in page_blocks:
            if block["type"] == "child_page":
                self.handle_page_block(block["id"], create_translation)
            else:
                self.handle_normal_block(block, realtime, create_translation)

        duration = datetime.now(timezone.utc) - task_start_time
        duration_seconds = duration.total_seconds()

        print(f"Conversion cycle took {duration_seconds} seconds\n")


if __name__ == "__main__":
    note_path = f"{pathlib.Path(__file__).parent.resolve()}/note.json"

    try:
        with open(note_path, "r", encoding="utf8") as file:
            note = json.load(file)
    except FileNotFoundError:
        note: dict[str, str] = {}

    is_note_modified = False
    if "googleCloudApiKey" not in note.keys():
        answer = input("\nEnter your Google Cloud API key\n")
        note["googleCloudApiKey"] = str(answer).strip()
        is_note_modified = True
    if "notionApiKey" not in note.keys():
        answer = input("\nEnter your Notion API key\n")
        note["notionApiKey"] = str(answer).strip()
        is_note_modified = True

    if is_note_modified:
        with open(note_path, "w", encoding="utf8") as file:
            json.dump(note, file, indent=4)

    google_cloud_api_key = note["googleCloudApiKey"]
    notion_api_key = note["notionApiKey"]

    answer = input("\nEnter the Notion page URL\n")
    root_page_id = str(answer).split("/")[-1].split("-")[-1]
    answer = input("\nWill you create translations, or remove them? (c/r)\n")
    create_translation = True if str(answer).lower().strip() == "c" else False

    source_language: Optional[str]
    target_language: Optional[str]
    if create_translation:
        answer = input("\nEnter the source language for translation (en/ko/ru/jp...)\n")
        source_language = str(answer).lower().strip()
        answer = input("\nEnter the target language for translation (en/ko/ru/jp...)\n")
        target_language = str(answer).lower().strip()
        answer = input("\nShould this translate in realtime and keep running? (y/n)\n")
        realtime = True if str(answer).lower().strip() == "y" else False
    else:
        source_language = None
        target_language = None
        realtime = False

    answer = input("\nWill you include subpages? (y/n)\n")
    include_subpages = True if str(answer).lower().strip() == "y" else False

    print("")

    converter = Converter(
        source_language,
        target_language,
        google_cloud_api_key,
        notion_api_key,
    )

    if realtime:
        while True:
            converter.convert_page(
                root_page_id,
                include_subpages,
                realtime,
                create_translation,
            )
            time.sleep(30)
    else:
        converter.convert_page(
            root_page_id,
            include_subpages,
            realtime,
            create_translation,
        )
