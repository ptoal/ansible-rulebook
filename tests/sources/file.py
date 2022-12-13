#  Copyright 2022 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import asyncio
import os

import yaml
from watchdog.events import RegexMatchingEventHandler
from watchdog.observers import Observer


def send_facts(loop, queue, filename):
    with open(filename) as f:
        data = yaml.safe_load(f.read())
        if data is None:
            return
        if isinstance(data, dict):
            loop.call_soon_threadsafe(queue.put_nowait, data)
        else:
            if not isinstance(data, list):
                raise Exception(
                    f"Unsupported facts type, expects a list of dicts"
                    f" found {type(data)}"
                )
            if not all(
                [True if isinstance(item, dict) else False for item in data]
            ):
                raise Exception(
                    f"Unsupported facts type, expects a list of dicts"
                    f" found {data}"
                )
            for item in data:
                loop.call_soon_threadsafe(queue.put_nowait, item)


def sync_main(loop, queue, args):

    files = [os.path.abspath(f) for f in args.get("files", [])]

    if not files:
        return

    for filename in files:
        send_facts(loop, queue, filename)

    class Handler(RegexMatchingEventHandler):
        def __init__(self, **kwargs):
            RegexMatchingEventHandler.__init__(self, **kwargs)

        def on_created(self, event):
            if event.src_path in files:
                send_facts(loop, queue, event.src_path)

        def on_deleted(self, event):
            pass

        def on_modified(self, event):
            if event.src_path in files:
                send_facts(loop, queue, event.src_path)

        def on_moved(self, event):
            pass

    observer = Observer()
    handler = Handler()

    for filename in files:
        directory = os.path.dirname(filename)
        observer.schedule(handler, directory, recursive=False)

    observer.start()

    try:
        observer.join()
    finally:
        observer.stop()


async def main(queue, args):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, sync_main, loop, queue, args)


if __name__ == "__main__":

    class MockQueue:
        def put_nowait(self, event):
            print(event)

    asyncio.run(main(MockQueue(), {"files": ["facts.yml"]}))
