"""
Realiza valizaciones a nivel global, sobre un conjunto de mallas

"""

from __future__ import annotations

import csv
import shutil
import datetime
import os
import base64
import time
import controlm as control
import controlm as utils

from xml.etree.ElementTree import parse
from pathlib import Path
from controlm import ControlRecorder
from controlm import ControlmContainer, ControlmDigrafo


if __name__ == '__main__':

    string_importante = "eFh4KysreHh4KysrKysreFh4KysreFh4eCsreHh4eHh4Kyt4eHh4KysreHh4eCsreHh4Kys6Li4uLi4uLi4uLi4uLi4uLi4uLjo7Kys7Li47eHh4eHh4eHh4WFh4eHh4WHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eFh4eHhYWFh4eFhYWFhYWFgkJFhYWCQkJFh4eHh4eCt4eA0KeHgrKyt4eHh4KysreFh4KysreHh4eHh4KysreHh4eCsreHh4eCsrK3greHh4Kyt4eHh4KysrOzs6Oi4uLi4uLi4uLi46OysreFhYWHh4eHh4eHh4eHh4WFhYeHh4eHh4eHgreHh4eHh4eHh4eHh4eHh4eHh4eHhYeHh4eHh4eHh4WFhYWHhYWFhYWFhYJFhYWFh4eHh4Kyt4WA0KKyt4eHh4KysreHgreHh4KysreHh4KysreFh4eCt4eHh4eHh4KysreFh4eCsreHhYeHh4eHgrKzs6Oi46Ojo6Li4uLi4uLi4uOjo7Kys7OjsreFhYWFh4WHh4eHh4eHh4eHhYWHh4eHh4eHh4eHh4WHh4eHh4eHh4eHh4WHh4eHhYWHh4WFhYWFhYWFgkWFhYWFh4eHh4KysrWA0KeHh4eHgrKyt4eHh4KysreHgrKysrKyt4eHh4KysreFh4eCsreFh4eHh4eHh4WFhYWFh4eHh4K3h4OzouLi4uLi4uLi4uLi4uOjo7KysrOzsreFhYWFh4WHh4eHh4eHh4eHh4eHh4eFhYeHh4WFhYeHh4eFhYWHh4WFhYeHh4WFh4eHh4WFhYeHhYWFhYWFhYJFh4eHh4KysreA0KeHgrKyt4eHgrK3grKysreHh4KysreHh4KysreHh4eHh4Kyt4eFhYeCt4WHhYWFhYWFhYWCRYeHgrKzs6Li4uLi4uLi4uLi4uOjsrKysrOjsrKyt4WFhYeFh4eHh4eHh4WHh4eHh4eHh4eHh4WFh4eHhYWFh4WFhYWFhYWFhYJFhYeFhYWFh4WFhYWFhYWFgkWHh4eHh4KysreA0KeHgrKyt4eHgrKyt4eHh4KysreHh4eHgrKysreHh4KysreHh4KysreHh4Ojt4WCQkJCQkJFhYeCsrOzo6Oi4uLi4uLi4uLjo6OzsrK3g7Oit4WFhYWFhYWHh4eHh4eHh4eHh4eHhYeHh4eFhYeHh4WFhYWHh4eFhYWHhYJCRYWFhYWFgkWFhYJCRYWFgkJFhYWFh4eHh4KysreA0KKyt4WHh4KysreHh4eHgrKyt4eHh4KysreHh4KysrKyt4eHh4KysreFgrOjtYJCQmJCQkJFhYeHh4Kys7Ozs6Oi4uLi4uOjs7K3h4eHgrK3h4eHhYeFhYWFh4eHh4eHh4eHhYeHh4eHh4eHh4eHh4WFh4eFhYWHh4eFhYWFhYeFgkJFhYWCQkWFhYWFgkJFhYWCRYeHh4KysreA0KKyt4eHgrKyt4WHh4KysreHh4eHgrK3h4eFh4KysreFh4KysreHh4eHg7K1gkJCQkJCRYWFgrOzo7Oys7Ozs7K3gkJiYmJiYmJiYmJCYmJiYmJiYkWHh4WFhYWFh4eHh4eHh4eHh4eFhYeHh4eFh4eHh4eFhYWHh4eFhYeHhYWFhYWFhYWCRYWFhYJCRYWFgkJFh4eHh4KysrKw0KeHgrKyt4eHh4eHgrKyt4eFh4Kyt4WFh4Kyt4eHh4eHh4eCt4eFh4Kyt4WCQkJCQkJFgkWFhYeHh4K1gkJiYmJiYmJit4JiYmJiYmOysmJiYmJiYmJiZYeFhYWFh4eHhYWHh4eFhYWHh4eHh4WFh4eHhYWFh4eFhYWHh4eHhYWFh4eFgkWHhYWCRYWFhYWCQkWFh4K3h4KysrKw0KeHgrK3h4eHgrKyt4eHh4eHgreHh4eHh4Kyt4WFh4Kyt4WFh4eHgrK3hYWFgkWFhYJFh4WFhYJCQmJiZ4JiYmJCs7Oi4uLi46Ojs7Kys6Ojt4eHh4WCQreCt4WFh4WHh4eHh4eHhYeHh4eCRYeHh4WFhYeFh4WFhYWHh4WCRYeHhYWFhYWFhYWCRYWFgkJFhYWFhYeCt4KzsrKw0KK3h4eHh4eHgrK3h4eHgrKyt4WHh4KysreHh4eHgrK3h4eFh4KysrK3hYWFgrWCQkJCRYWCQmJiYmJiZ4Ozs6Ojo6Ojo6Ojo6Ozs7Kys6O3h4eHh4eHh4eDs7WHh4WHh4eHhYWHh4eHhYeHh4eHhYWFh4eFgkJHh4eFhYWFhYWFhYJFh4WCQkWHhYWFhYWFhYWFhYeCt4Kzs7Kw0KK3hYWHgrKytYWHh4KysreHh4eHh4K3h4WFh4Kyt4WFh4KysreCsrK3h4eHhYWCQkJFgmJiYmJiZYKysrKzs6Ozs7Ozs7Ozs7OysrKys7eHh4WFh4eHh4KzouK3h4K3h4eHh4eHh4eHhYeHh4WFhYeHhYWFhYWHh4WCQkeHhYJCRYeFhYWFhYWFhYJFhYeFgkWFh4Kyt4Kys7Kw0KeHh4eHgreHh4WHgrKyt4WFh4Kyt4WFh4eHh4eHh4eFh4Kyt4WFh4K3h4eFgkJCQkJCYmJiYkWFhYeHh4KysrOzs7Ozs7Ozs7KysreHh4WFhYeHh4Kzs7Oi4uO3hYeHh4WHh4K3hYeHh4eHh4eHh4eHhYJFh4eFgkWHh4WFhYWFh4eFgkJHh4WCQkWHhYWFhYWFh4Kyt4Kys7Kw0KWHgrK3hYWHgrKyt4eHgreHgrK3h4WFh4Kyt4JCRYeCt4WFh4eHh4eHh4WCRYJFgkJCYmJHh4WFhYWFh4eCsrKysrOyt4WCQmJiYmJiYmJiYkJCQkWFh4eCsrK3hYWHh4eHh4eHhYeHh4eFhYeHh4WFh4eHh4WFhYWHh4WCRYeHhYJFh4eFhYWFhYeHhYJFh4eFhYeCsrKys7Kw0KeHhYeHhYWHgrK3hYWFh4Kyt4WFh4Kyt4eHh4eHh4eHh4JCRYKyt4WFh4WFhYJCQkOyRYWFhYWCQkWFhYWFhYJCYmJiYmJiYkJCQmJiYmJiYmJiYmJiYmJCRYeHhYWCsreHhYJHh4eFgkWHh4eHhYWFh4eHgkJFh4eFhYWHh4eFhYWFh4eFgkWHh4WFhYeHhYWFh4eCsrKys7Kw0KeFgkJHgrK3gkJHh4eHh4eHh4WHh4K3h4WFh4Kyt4WFh4eHh4eFh4WFgkWFhYWFhYJFhYWFhYJFgkJCQkJiYmJiYkJFhYWCQkJCRYWFhYWFhYWFhYWFgkJCYmJiRYWFh4WHh4eHh4eFhYeHh4WCRYeHhYJFhYWFhYWFhYeHh4JCR4eHhYWFh4eHhYWFh4eHhYWHh4KysrKys7Kw0KeHh4eHgreHhYJFgrK3gkJFh4K3h4WHh4eHh4K3h4WFh4K3h4WFh4KytYK1hYWFhYWFhYWFgkJCQmJiYmJiYkJFhYJCQkJCQkJCQkWHh4eHh4eHh4eHh4eCQmJiYmJHh4WHgrK3gkWHh4eFhYWHh4eFhYJFh4eFgmJHh4WCRYWHh4eFhYWHh4eFhYeHh4WFh4eFh4eCsrKys7Kw0KeCsrK3h4eHh4Kyt4eHh4WHgrK3hYJCR4KytYJFh4K3h4WHh4eHh4K3hYWFhYWFhYWFhYWFgkJiYmJiRYWCRYWCQkJCRYWHh4WFgkJFh4eHgreHh4eHh4eFgmJCtYJiR4eHhYWHhYeHh4eCQkeHh4JCRYeHhYWFhYeHh4WCRYeHhYJFh4eHh4eHh4eHh4WHh4eFhYeCt4Kys7Kw0KeHh4eHh4eCsrK3h4eHgrKyt4eHh4eHh4eHh4WFh4K3hYJCR4Kyt4JFhYWFhYWFhYWFhYJCYmJiRYWFhYWFhYWCQkeFgkJiYmJiYmJngrKysrKyt4eHh4eHgmJDt4JCYkeHgkJHh4eFgkWHh4WFhYWFh4eHhYJHh4eFgkWHh4WFhYeCQmJiYkJCsuLi4uLjo7K3h4eCt4Kys7Kw0KeFhYWHh4eHhYeHh4eHh4eHh4eHgrKyt4eHgrKyt4eHh4eHgrK3h4WFh4eFhYWFhYWCQmJiYkWFhYWFh4eHh4WCQkJiYmJiYkWFhYKzsrKysrKysreHh4K3gkWDs7WCQkJFhYeHgreFhYWHh4WCRYeHhYJFh4eHh4WHh4eHh4WFh4JCYkJCQkJiYkKy4uLjouLi46Kyt4Kys7Kw0KeFhYeHgreFhYWHgrK3hYWHh4eHh4WHh4eHh4K3h4eHgrKyt4eHgrKysrK3gkWFhYJCYmJlhYWFhYeHh4eHh4WCYmJCRYWFh4Ozo7Kzs7OysrKysrKysrK3hYeDsreCRYOzo6Ojo7OzsreFhYWHh4eHhYWFh4eHhYWHgreFhYeHhYJiYkJiYkJiYmJCQrLi46Oi4uLjo7KysrKw0KeHh4eFgkeHh4eHh4eHhYWHh4eHhYWFh4K3hYWFh4eHh4eHh4eHgrKyt4eHhYWFgkJiYmJlhYWFhYeHh4eHh4KysrOzs7OzsreFhYeHgrOzs7KysrKysrK3hYJiR4O1hYKysrKysrOzsrWFhYeDs6WCR4KysuLnh4eHh4eHh4eHhYJnh4eDs6Ojo6eCRYWDouOjo6Ojo6OjsrKw0KKysreFhYeCsreFhYWHgreHhYWHh4WHh4eHhYJFh4K3hYJFh4eHhYWHh4eHh4WFgmJiQmJlhYWFhYeHh4eHgrK3h4WFhYWCQkWFhYJCR4LngkJHgrK3gkJCYmJiZYOytYeCsrKyt4Ozt4WHh4eDsuK3h4eCs7OisreFhYeHgreFgkWCQmJHg6Li4uLi47WFgrLjo6Ojo6OjorKw0KK3h4eHgrK3h4eHh4eCsrK3hYWHgrK3hYWFh4eHh4eHh4WHh4eHh4JFh4K3h4eCQmJCQkJiZYWFhYeHh4eHgrK3hYWCQkeCs7Ojo7JiYkJCsmJiYmJiYmJiYmJHhYWDsrWCs7KysrOyt4eHh4eCsrKysrKysrKzs7Ozs7Ozs7Ojo7OyskJiZ4Li4uLi4uLjtYeDo6Ojs6OjsreA0KOjo6Ozs7OysrKysrK3h4eHh4eCt4eHh4eHgrK3hYWHgrK3hYWFh4eHh4WFh4eCQmWFgkWCQmJFhYWFhYWHgkJiQrWCsrWCYmJiYmJiYkJiYmJiYmJiYmJiR4KzsreHh4KysrKysrOzs7Ozs7Ozs7Ozo6Ojo6Ojo6Ojo6Ojo6Ojo6Li4uKyYmOy4uLi4uLi4uWFg6Ojo6Ojo7Kw0KOzs6Ojo6Ojo6Ojo6Ojs7Ozs7OzsrKysrKyt4eHh4KysrKyt4eHgrK3h4WHh4KyQmWFhYJCQkJCQkJCQkJCYmJiQkJCYkJiYkJCYmJiYmJiYmJCQmJiYmJFgrKysrOzs7Ozs7Ozs6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Oi46Ojo6Ojo6Oi4uLismJDouLi4uLjo6OiskKzo6Ozs7Ow0KWFhYWFh4eCsrKys7Ozs7Ozs6Ojo6Ojo6Ojs7Ozs7OzsrKysrKyt4eHgrKysrKyskJHhYJCQkJCYmJiYkJCYmJCQmJiYmJCYmJiYmJiYmJiYmJiYmJDsrKys7Ozs7Ozo6Ojo6OjouLi4uLi4uLi4uLi4uLi4uLi4uLi46Ojo6Ojo6Ojo6LjokJnguOjo6Ozs7Ozs7JFg7OzsrOw0KeFh4eHh4eHh4eFhYWHh4eHh4eHgrKysrOzs7Ozs7Ozs7Kzs7Ozs7Ozs7OzsrKysrK3hYWCQkJCYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYkJHg7Ozs7Ojo6Ojo6Oi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi46Ojo6Ojo6Ojo6Ojp4WCQ7Ojo6OzsrK3h4K1hYK3grOw0KWFhYeCsreHh4eCt4eHh4eHh4eHh4eHhYWHg6OlhYeHg7LjsrKzs7Ozs7Ozs6Oyt4K3h4WFhYeHgrKyt4eFgkJCYmJiYmJiYmJiYkJFh4Kzs6Ozs7Ojo6Ojo6Li4uLi4uLi4uLi4uLiAgICAgICAgLi4uLi4uLi4uLi4uLjo6Ojo6Ojo6Ojp4eCQkOjs7Ozs7OytYLjp4JCs7Ow0KeHgrKys7Ozs7OjsreFhYWHgrK3hYWHh4eHg6Onh4eHh4Ozt4eHgrKysrKzs7Ozs7Ozs7Ozs7Ojo6Ozo6Ojo6Ojs7Ozs7OjouLi4uLi4uLjo7Ozo6Ojo6Oi4uLi4uLi4uICAuLiAuICAgICAgICAgIC4uLi4uLi4uLi4uOjo6Ojo6Ojs7Ojp4K1gmOzo7Ozs7Ozo6Ojt4eHg7Og0KKysrOzo6Oi4uLi4reHh4eHh4eHhYWHgrK3grOysrKyt4eDs7Ozs7Ozs7Ojo6Ojo6Ojo6OjouLi4uLi4uLi4uLi4uLjo6Oi4uLi4uLi4uLis7Ojo6OjouLi4uLi4gLiAgICAgICAgICAgICAuLi4uLi4gLi4uLi4uLjo6Ojo6Ojs7Ozs7OztYeFgmJDs7Ozs7Ozs6Ojo6Ojo6Og0KKzs6Li4uLi4uLi54eCsreFh4eCsrKzs7eFgrJCtYeCsrOzo6Ojo6Ojo6Ojo6OjouLi4uLi4uLi4uLi4uLi4uLi4uLi4uOis6Li46Ojo6OngrOjo6Oi4uLi4uLi4gICAgLi4uLi4uLi4uLi4uLi4uLi4uLi4uOjo6Ojo6Ojs7Ozs7Ozs7OyskeCQmJis7Ozs7Ozs7Ojo7Ozs7eA0KOzsuLi4uLi4uLjp4Kzs7KysrKysrOzsreDs7Ojo7OngrOjo6Ljo6OjouLi4uLi4uLi4uLi4uLi4uLiAgICAgIC4uLi4uLisrOjo7Ozo6OngrOi4uLi4uLi4gICAuLi4uLi4uLi4uLi4uLi4uLi4uLi46Ojo6Ojo6Ozs7Ozs7KysrKys7KyQkWCYmJiR4KysrKzs7Ozo6Ojo6Ow0KOzouLi4uICAuLisrKzo6OysrOzs7Ozo7eDpYK3hYOlgrLi4uLi4uLi4uLi4uLi4uLi4uLi4uICAgICAgICAgICAuLi4uLjsrOjo6Ojo6Oit4Oi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLjo6Ojo6Ojo7Ozs7Ozs7KysrKysrKyt4JCQkWCQmJiZ4eHh4KysrOzs7Ozs7Ow0KOi4uICAgICAuLis7Oi4uOysrOzs7Ojp4JDokKyt4LjouLi4uLi4uLi4uLi4gICAgICAgICAgICAgICAgICAgICAgIC4uLjorOi4uOjouLjt4Oi4uLi4uLi4uLi4uLi4uLi4uLjo6Ojo6Ojo6Ojo7Ozs7Ozs7KysrKysrK3h4eHhYJFhYWCQmJCQmJiZYWHh4eCsrKzs7eCQmJg0KOi4uLi4uLi4uOjs6Li4uOysrKys7OjsreDo6Ojo6Ojo6Oi4uLi4uLi4gICAgICAgICAgICAgICAgICAgICAgICAuLi4uLi4rOy4uLjouLjp4WFgrLi4uLi4uLi4uOjo6Ojo6Ojo7OzsrK3h4eHhYWFhYWFgkJCQkJCYmJiYmJiYmJFhYWCYmJiYmJiZYWHh4eHgrK3gmJiYmJg0KLi4uLi4uKzsuOjo6Li46OysrKzs7Ojs7Ozo6Ojs7Ozo6Li4uLi4uLi4gLi4gICAgICAgICAgICAgLi4uLi4uLi4uLi4uO1hYKy4uLi4uLi54WFgkJCRYKzo6OjsreHh4WFgkWFhYKyskJCQkJCQkJCtYJCQmJiYmJiYmJiYmJiYmJiQkWCYkWFgmJiYkWFhYWHgreCQmJiZ4Ow0KLi4uLi4uLi4uOy46Li47OysrKys7Ozs6Ozs6Ojo6Oi4uLi4uLi4uLi4gIC4uLi4uICAuLi4uLi4uLi4uLi4uLi4uLitYWCQkWC4uLi4uLi4uOlgkWCQkWFhYWFg7O1gkJCQkJCRYKyskWCQkJCQkWFh4JCQmJiYmJiYmJiYmJiYmJiYmJFh4WFgmJiYmJCQkJHgrJCYmJFh4Ow0KLi4uLi4uLi4uLi4uLi47O3grKysrOzs7Ozo6Ojo6Oi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi47JCQkJCQrLi4uLi4uLi4uLi4uLngkWFhYWFh4O3hYWFhYWFgkWCskJCQkJFh4WFgreHh4eHhYWFhYeHh4eHgreHh4eHg7eHgkJiYmJiQmJlgrJiYmJFgkeA0KLi4uLi4uLi4uLi4uLjp4K3h4KysrOzs7Ozs7Ozo6Ojo6Ojo6Ojo6Ojo6OjouLi4uLi46Ojo6Ojo7OzsrKyt4eHhYJCQkWC4uLi4uLi4uLi4uLi4uLi4uLjsrKyt4Kys6Li4uOjo6KysrOzs7Ozs7Kyt4KysreHh4eHh4eHh4eHh4eHh4eHg7K3h4JiYmWCt4WHgrJiQmJCRYeA0KLi4uLi4uLi4kJiY6Ljt4eHhYKysrKzs7Ozs7Ozs7Ozs7Ozs7Ojo6Ojo6Ojo7Ozs7OysrK3h4eHh4eHh4Ozt4WFgkJFg7Li4uLi4uLi4uLi4uLi4uLi4uLi4uLi46Kys6Ojo6Ozs7Oyt4Ozs7OzsrKyt4KysrKysrK3h4eHh4eHh4eHh4eHgreHh4JCYmWHh4Kyt4JCQkJCQkWA0KLi4uLi4uLjs6Olg6Oyt4WHhYJHgrOzs7Ozs7Ozs7Ozs7Ozs7OzsrK3hYWFhYWFhYWFgrO1hYWFhYWFhYeDt4WCQkKy4uLi4uLi46OzsuLi47Oy4uLi4uLi4uOi4uOys7Ojo7Ozs7OysrOzs7OysrKysreDsrKysrKysreHh4eHh4eHh4eHh4eHhYWCYmJFh4eHh4eCRYJCQkJA0KLi4uLi4rWHguO1gkJiYmJiYmJiYmJFhYeHh4eHh4WFgkJCYmJiYkJFgrWCQkJCQkJFh4O1gkWFhYeCs6Ojs7Li4uLi4uLi4uLi46OysrOjs7Ozs6Ozs7OzouOjo6Oys7Ojo7Ozs7Ozt4Ozs7Ozs7Ozs7OzsrKysrK3h4eHh4eHh4eHh4eHh4JFgkWCYmJlhYeHh4eHhYJCQkJA0KLi46WFhYWCQkJiYmJiYmJiYkJiYmJiYmJiYmJiYmJiYmJiYmJiYmJFgrWCQkJFhYeCsrOys6Oi4uLi4uOjs7Li4uLi4uLi46Ozs7Ozo6OjouLi4uLjo6Ojo7Kzs7OysrOzs7Ozs7Ozs7Ozs7OzsrKys7KysrKysrKyt4eHh4eHh4eHh4eHh4JFgkWCQmJiRYWHh4eHh4JCQkJA0KLnhYJCYmJlgrOzs7K3gkJiYrWCQmJiYmJiYmJiYmJiYmJiYmJiRYeCsreDs7Ozs7Ozo7Kys6Ojo6Ojo6Ojs7Ojo6Ojo6Kzs7Ozo6Li4uLjo6Ozs7Ozs6Ojo6Oyt4KzsrOzs7OysrKzs7Ozs7OysrOzsrKysrKyt4eHh4eHh4eHh4eHh4eHh4WFgkWCQmJiYkWFh4KysrWCYmJg0KWCQmJiRYeCs6Li4uLjp4JCYkWFgkJiYmJiYmJiYmJFh4KysrOzs7OzorKzs7Ozs6Ojo6Kys6Ojo6Ojo6Ojt4Ojo6OjsrKys7OitYJCQkJCYkJCQkJCQkJCQkJFgrK3grKysrKysrKysrKzsrKysrKysrKysrKysreHh4eHh4eHh4eHh4eHh4WFhYJCQmJiYmJFh4eCt4eCQmJg0KJCYmWFh4KzsuLi4uLjt4JCZ4WFhYWFhYeHgrKys7Ozs7Ozs7Ozs7Ozs7Kzs7Ozs7Ozo6Oys6Ojo6Ojo6OjorOjs7eHgrK1gkJiYkJCYmJiYmJiYmJiYmJiYmJiZ4KysrKzsrKysrKysrKysrKysrKysrKysrKyt4eHh4eHh4eHhYWFhYWFhYWCRYJCQmJiYmJiRYWHgrJCYkJA0KJFhYWFh4OzouLi4uLjt4JCZYeFhYeHh4eCsrKzs7Ozs7Ozs7Ozs7Ozs6Ozs6Ozs6Ojs7Ois6Ojo6Ozs7OzsrOzt4eHgkJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmWCs7K3grKysrKysrKysrKysrKysrKysrK3h4eHh4eFhYWFhYWFhYWFhYWCRYJCYmJiYmJiYkJCYmJCYmJA0KeHhYWHgrOi4uLi4uLitYJCYkeFh4eHh4KysrOzs7Ozs7Ozs7Ozs7Ozs6Ojo6Ojo6Ojo7Ojo7Ozs7Ozs7Ozs6Oit4O3gmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiQrOzsrKzs7KysrKysrKysrKzsrKyt4eHh4eHhYWFhYWFhYWFhYWFhYWCRYJCYmJiYmJiYmJiYkWFgkJg=="
    omitir_robotesto = True

    try:
        os.mkdir("CONTROLES")
    except FileExistsError:
        shutil.rmtree("CONTROLES")
        os.mkdir("CONTROLES")

    path = Path()
    files = [file for file in path.iterdir() if file.name.endswith('.xml')]
    if len(files) > 1 or len(files) == 0:
        raise Exception(f"Asegurarse de que exista solamente 1 xml en el directorio de trabajo")
    else:
        xml_prod = str(files[0])
    base = parse(xml_prod).getroot()

    acumulador_errores = {
        'headers': ['MALLA', 'JOBNAME', 'DESCRIPCION'],
        'errores': []
    }

    if not omitir_robotesto:
        print("\n\niniciando controles...", end="")
        time.sleep(1)
        print("ooooooo", end="")
        time.sleep(2)
        print("ooooooOOOOOOOOOOOOOOOO0000000000000000000000")
        time.sleep(3)
        for char in base64.b64decode(string_importante).decode('utf-8'):
            time.sleep(0.00007)
            print(char, end='')
        print('\n')

    contenedor = ControlmContainer(base)

    for malla_prod in contenedor.mallas:

        print(f"Controlando {malla_prod.name}")

        crono_start = time.perf_counter()
        control_record = ControlRecorder()

        # Comenzamos a analizar job por job
        for work_job in malla_prod.jobs:

            try:
                control.jobname(work_job, malla_prod, control_record)
                control.application(work_job, malla_prod, control_record)
                control.subapp(work_job, malla_prod, control_record)
                control.atributos(work_job, malla_prod, control_record)
                control.variables(work_job, malla_prod, control_record)
                control.marcas_in(work_job, malla_prod, control_record)
                control.marcas_out(work_job, malla_prod, control_record)
                control.acciones(work_job, malla_prod, control_record)
                control.recursos_cuantitativos(work_job, malla_prod, control_record)
                control.cadenas_malla(malla_prod, control_record)
            except Exception as err:
                msg = f"Ocurrió un error inesperado al realizar controles sobre el job [{work_job.name}] contactar a Tongas"
                raise Exception(msg) from err

        informacion_extra_recorders = {
            'jobnames_ruta_critica': [job.name for job in malla_prod.jobs if job.es_ruta_critica()]
        }

        sec, millisec = divmod((time.perf_counter() - crono_start), 1000)
        control_record.add_inicial(f"Fecha de generación [{datetime.datetime.now()}]")
        control_record.add_inicial(f"Malla analizada [{malla_prod.name}]")
        control_record.add_inicial(f"UUAA: {malla_prod.uuaa}")
        control_record.add_inicial(f"Periodicidad: {malla_prod.periodicidad}")
        control_record.add_inicial(f"Cantidad jobs {malla_prod.name}: {len(malla_prod.jobs)}")
        control_record.add_inicial(f"Tiempo empleado: {sec}s:{round(millisec, 3)}ms")
        control_record.add_inicial('-' * 70)
        control_record.write_log(f'CONTROLES_{malla_prod.name}.log', informacion_extra_recorders)

        for item_key, item_list in control_record.info.items():
            if item_key != 'INICIAL':
                for item in item_list:
                    acumulador_errores['errores'].append([malla_prod.name, item_key, item.strip()])

        print(f"Análisis finalizado para {malla_prod.name}, log generado")
    print("Controles finalizados")

    # Con global no me refuero a uuaas globales, sino que cosas a nivel xml entero y no puntualmente sobre cada malla
    print("Generando digrafo global")
    jobs_global = []
    for malla_global in contenedor.mallas:
        jobs_global.extend([job for job in malla_global.jobs])
    digrafo_global = ControlmDigrafo(jobs_global)
    print("Digrafo global generado")

    print("Escribiendo archivos cadenas globales")
    with (open(f"cadenas_global_nomina.csv", 'w', newline='', encoding='utf-8') as f_nomina,
          open(f"cadenas_global_indice.csv", 'w', newline='', encoding='utf-8') as f_indice):

        csv_writer_cadena_global_nomina = csv.writer(f_nomina)
        csv_writer_cadena_global_nomina.writerow(["ID_CADENA", "JOBNAME", "MALLA", "FASE", "DATAPROC"])

        csv_writer_cadena_global_indice = csv.writer(f_indice)
        csv_writer_cadena_global_indice.writerow(["ID_CADENA", "JOBS", "CANT_JOBS"])

        for index, cadena in enumerate(digrafo_global.obtener_arboles()):

            cadena_id = str(index).zfill(3)
            for jobname in cadena:
                job = contenedor.get_job(jobname)
                csv_writer_cadena_global_nomina.writerow([cadena_id, job.name, job.atributos['PARENT_FOLDER'], utils.oofstr(job.fase), job.dataproc_id])

            csv_writer_cadena_global_indice.writerow([cadena_id, "|".join([jobname for jobname in cadena]), len(cadena)])
    print("Archivos cadenas globales escritas")

    print("Controlando cadena global")
    control.cadenas_global(digrafo_global, contenedor)
    print("Finalizando cadena global")

    if acumulador_errores:
        with open(f"errores_global.csv", 'w', newline='', encoding='utf-8') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow(acumulador_errores['headers'])
            for row in acumulador_errores['errores']:
                csv_writer.writerow(row)