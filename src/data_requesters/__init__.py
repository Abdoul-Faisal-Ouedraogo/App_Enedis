# Import the ADEME data requester
from .ademe import Ademe_API_requester

# Instantiate the requester to be shared across the app.
api_ademe = Ademe_API_requester()