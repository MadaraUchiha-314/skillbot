- Create a folder called `channels` under `skillbot`
- Move `cli` and `streamlit` under channels
- Move re-usable parts of "chats" from `cli` and `streamlit` to a single file
    - Other channels when introduced will re-use these chat primitives
- Update imports and documentation

Updates:
- Keep cli as a separate folder under `skillbot`
- CLI Chat is the "channel"
- CLI has other functionalities
- What's the point of creating `ChatResponse` class ?
    - `ChatResponse` is just Task | Message
        - Why create a new type ? Just follow A2A
    - Every "message" should just follow the A2A model of `Message`
    - Keep the utilities for doing things with `Message` like extracting artifacts