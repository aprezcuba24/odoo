# Part of Odoo. See LICENSE file for full copyright and licensing details.

from .utils.local_dotenv import load_local_dotenv

load_local_dotenv()

from .hooks import post_init_hook  # noqa: F401  # manifest post_init_hook

from . import controllers
from . import models
from . import wizards
