# :postbox: Stamp Appraiser

Upload a photo of a postage stamp and get an AI estimate of:

- **What it is**: name, subject, face value and catalog number
- **Where it's from**: issuing country
- **When it was issued**: year or period
- **How much it's worth**: a market value range in USD, based on the condition visible in the photo

The stamp is identified with Claude's vision model through the Anthropic API.

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Provide an Anthropic API key (get one at https://console.anthropic.com), either as an
   environment variable:

   ```
   $ export ANTHROPIC_API_KEY=sk-ant-...
   ```

   or in `.streamlit/secrets.toml`:

   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```

   If neither is set, the app asks for a key on the page.

3. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```

When deploying to Streamlit Community Cloud, add `ANTHROPIC_API_KEY` under the app's
**Settings → Secrets**.

> Valuations are AI estimates from a photo, not a professional appraisal.
