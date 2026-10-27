# Import the data requester
from .ademe import Ademe_API_requester
from .geo_features import Geo_API_requester

# Instantiate the requester to be shared accross the app.
api_ademe = Ademe_API_requester()
geo_api = Geo_API_requester()
