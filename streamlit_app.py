import base64
import os

import anthropic
import streamlit as st
from pydantic import BaseModel, Field

# Set the title and favicon that appear in the Browser's tab bar.
st.set_page_config(
    page_title='Stamp Appraiser',
    page_icon=':postbox:',
)

MODEL = 'claude-opus-5-5'

SUPPORTED_TYPES = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'webp': 'image/webp',
    'gif': 'image/gif',
}

SYSTEM_PROMPT = """You are an expert philatelist and stamp appraiser.
The user will send a photo of a postage stamp. Identify it as precisely as you
can: the issuing country, the year or period of issue, what it depicts, its face
value, and the catalog number (Scott, Stanley Gibbons, Michel or Yvert) if you
recognise it.

Then estimate its current market value in US dollars as a low-high range, the
way a dealer would price a typical example. Take into account what you can see
of its condition: centering, perforations, gum, hinge marks, postmark/cancel,
tears, thins, fading or creases. Most stamps are common and worth very little,
so say so honestly when that is the case; do not inflate values.

If the image is not a stamp, or is too blurry to identify, say so in the
summary, set confidence to "low" and leave the fields you cannot determine as
"Unknown"."""


# -----------------------------------------------------------------------------
# Declare some useful functions.

class StampAppraisal(BaseModel):
    is_stamp: bool = Field(description='Whether the image actually shows a postage stamp.')
    name: str = Field(description='Short descriptive name of the stamp, e.g. "Penny Black".')
    country: str = Field(description='Issuing country or postal authority.')
    year_issued: str = Field(description='Year (or range of years) the stamp was issued.')
    face_value: str = Field(description='Denomination printed on the stamp.')
    subject: str = Field(description='What the stamp depicts or commemorates.')
    catalog_number: str = Field(description='Catalog reference(s) if known, otherwise "Unknown".')
    condition: str = Field(description='Assessment of the condition visible in the photo.')
    value_low_usd: float = Field(description='Low end of estimated market value in USD.')
    value_high_usd: float = Field(description='High end of estimated market value in USD.')
    confidence: str = Field(description='"low", "medium" or "high" confidence in the identification.')
    summary: str = Field(description='A few sentences of history and what drives this stamp\'s value.')
    tips: str = Field(description='Advice for the owner, e.g. whether to get it expertised or how to store it.')


def get_api_key():
    """Read the Anthropic API key from Streamlit secrets or the environment."""
    try:
        if 'ANTHROPIC_API_KEY' in st.secrets:
            return st.secrets['ANTHROPIC_API_KEY']
    except FileNotFoundError:
        pass
    return os.environ.get('ANTHROPIC_API_KEY')


def appraise_stamp(api_key, image_bytes, media_type, notes):
    """Send the stamp photo to Claude and get back a structured appraisal."""
    client = anthropic.Anthropic(api_key=api_key)

    prompt = 'Please identify and appraise this stamp.'
    if notes:
        prompt += f'\n\nExtra information from the owner: {notes}'

    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        betas=['server-side-fallback-2026-07-01'],
        fallbacks='default',
        output_config={'effort': 'high'},
        system=SYSTEM_PROMPT,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': media_type,
                        'data': base64.standard_b64encode(image_bytes).decode('utf-8'),
                    },
                },
                {'type': 'text', 'text': prompt},
            ],
        }],
        output_format=StampAppraisal,
    )

    if response.stop_reason == 'refusal':
        raise RuntimeError('The model declined to appraise this image.')
    return response.parsed_output


def format_value(low, high):
    if high < 1:
        return 'Under $1'
    if round(low) == round(high):
        return f'${high:,.0f}'
    return f'${low:,.0f} – ${high:,.0f}'


# -----------------------------------------------------------------------------
# Draw the actual page

'''
# :postbox: Stamp Appraiser

Upload a photo of a postage stamp and find out where it's from, when it was
issued, and roughly how much it's worth.
'''

''
''

api_key = get_api_key()
if not api_key:
    api_key = st.text_input(
        'Anthropic API key',
        type='password',
        help='Set ANTHROPIC_API_KEY in your environment or .streamlit/secrets.toml to skip this.',
    )

uploaded_file = st.file_uploader(
    'Photo of your stamp',
    type=list(SUPPORTED_TYPES),
    help='A clear, well-lit, straight-on photo works best. Include the perforations.',
)

notes = st.text_input(
    'Anything else you know? (optional)',
    placeholder='e.g. "found in my grandfather\'s album, back has no gum"',
)

if uploaded_file:
    st.image(uploaded_file, caption='Your stamp', width=300)

appraise = st.button(
    'Appraise my stamp',
    type='primary',
    disabled=not (uploaded_file and api_key),
)

if appraise:
    extension = uploaded_file.name.rsplit('.', 1)[-1].lower()
    media_type = SUPPORTED_TYPES.get(extension, uploaded_file.type)

    with st.spinner('Examining your stamp...'):
        try:
            result = appraise_stamp(api_key, uploaded_file.getvalue(), media_type, notes)
        except anthropic.AuthenticationError:
            st.error('That API key was rejected. Please check it and try again.')
            st.stop()
        except anthropic.RateLimitError:
            st.error('Too many requests right now. Please wait a minute and try again.')
            st.stop()
        except anthropic.APIStatusError as e:
            st.error(f'The appraisal service returned an error: {e.message}')
            st.stop()
        except anthropic.APIConnectionError:
            st.error('Could not reach the appraisal service. Check your internet connection.')
            st.stop()
        except RuntimeError as e:
            st.error(str(e))
            st.stop()

    if not result.is_stamp:
        st.warning(result.summary)
        st.stop()

    ''
    st.header(result.name, divider='gray')

    col1, col2, col3 = st.columns(3)
    col1.metric('Estimated value', format_value(result.value_low_usd, result.value_high_usd))
    col2.metric('Country', result.country)
    col3.metric('Issued', result.year_issued)

    ''

    st.markdown(f'''
| | |
|---|---|
| **Face value** | {result.face_value} |
| **Subject** | {result.subject} |
| **Catalog number** | {result.catalog_number} |
| **Condition** | {result.condition} |
| **Confidence** | {result.confidence.capitalize()} |
''')

    ''
    st.subheader('About this stamp')
    st.write(result.summary)

    st.subheader('Tips')
    st.write(result.tips)

    st.caption(
        'This is an AI-generated estimate from a photo, not a professional '
        'appraisal. For valuable stamps, get a certificate from a recognised '
        'expertising service before buying or selling.'
    )
