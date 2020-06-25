# smartmirror.py
# requirements
# requests, feedparser, traceback, Pillow

from tkinter import *
import locale
import os
import re
import socket
import sys
from html import unescape
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
import traceback
import feedparser

from PIL import Image, ImageTk
from contextlib import contextmanager

LOCALE_LOCK = threading.Lock()
_LOG_PATH = Path(__file__).resolve().parent / 'smartmirror.log'


def _log(message):
    line = '%s %s\n' % (datetime.now().isoformat(), message)
    try:
        with open(_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line)
    except OSError:
        pass
    print(message, flush=True)


def _network_ready():
    for host, port in (('1.1.1.1', 53), ('8.8.8.8', 53)):
        try:
            socket.create_connection((host, port), timeout=3)
            return True
        except OSError:
            continue
    return False


def _fetch_rss(url):
    resp = requests.get(
        url,
        timeout=20,
        headers={'User-Agent': 'smart-mirror/1.0'},
    )
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def _clean_headline(text):
    """Quita HTML dos titulares RSS (p.ex. <span lang=\"gl\"> de La Voz de Galicia)."""
    if not text:
        return text
    text = unescape(str(text))
    text = re.sub(r'<[^>]+>', '', text)
    return ' '.join(text.split())

ip = '83.32.43.184'
ui_locale = 'gl_ES.utf8'            # idioma do reloxo/data
date_format = "%d %b, %Y"           # formato de data
news_feeds = [
    ('El País', 'http://ep00.epimg.net/rss/ccaa/galicia.xml'),
    ('20minutos', 'https://www.20minutos.es/rss/'),
    ('LVdG', 'https://www.lavozdegalicia.es/carballo/index.xml'),
]
news_headlines_per_feed = 5         # noticias por periodico
news_headlines_total = 15           # cantidade de novas a ver
meteogalicia_api_key = ''           # api key Meteogalicia
weather_lang = 'gl'                 # descripcion do tempo
weather_unit = 'metric'             # metric (C) ou imperial (F)
location_name = 'Muxía'             # nada para detectar por coordenadas
latitude = '43.10472'               # nada para detectar por ip
longitude = '-9.21806'
xlarge_text_size = 57               # tamaños de texto
large_text_size = 94
medium_text_size = 20
small_text_size = 14
start_fullscreen = True             # pantalla completa ao abrir
startup_fetch_delay_ms = 2000       # espera tras run-mirror.sh (rede)
startup_retry_interval_ms = 5000    # reintento se falla a carga
startup_retry_max = 72              # ~6 min de reintentos ao arranque
data_refresh_interval_ms = 600000   # actualización periódica (10 min)

_resolved_ui_locale = None

def _locale_candidates(name):
    if not name:
        return ['']
    candidates = [name]
    if '.' not in name:
        candidates.extend((f'{name}.UTF-8', f'{name}.utf8'))
    if name.startswith('gl_'):
        candidates.extend(('es_ES.UTF-8', 'es_ES.utf8', 'es_ES'))
    return candidates

def _resolve_ui_locale(name):
    global _resolved_ui_locale
    if _resolved_ui_locale is not None:
        return _resolved_ui_locale
    if not name:
        _resolved_ui_locale = ''
        return ''
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        for cand in _locale_candidates(name):
            try:
                locale.setlocale(locale.LC_ALL, cand)
                _resolved_ui_locale = cand
                locale.setlocale(locale.LC_ALL, saved)
                if cand != name:
                    print(
                        f"Locale {name!r} not available; using {cand!r}",
                        file=sys.stderr,
                    )
                return cand
            except locale.Error:
                continue
        locale.setlocale(locale.LC_ALL, saved)
    _resolved_ui_locale = ''
    print(
        f"Locale {name!r} not available; using system default",
        file=sys.stderr,
    )
    return ''

@contextmanager
def setlocale(name): #thread proof function to work with locale
    name = _resolve_ui_locale(name)
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            if name:
                yield locale.setlocale(locale.LC_ALL, name)
            else:
                yield saved
        finally:
            locale.setlocale(locale.LC_ALL, saved)

# MeteoGalicia sky_state -> assets
icon_lookup = {
    'clear-day': "assets/Sun.png",  # clear sky day
    'wind': "assets/Wind.png",   #wind
    'cloudy': "assets/Cloud.png",  # cloudy day
    'partly-cloudy-day': "assets/PartlySunny.png",  # partly cloudy day
    'rain': "assets/Rain.png",  # rain day
    'snow': "assets/Snow.png",  # snow day
    'snow-thin': "assets/Snow.png",  # sleet day
    'fog': "assets/Haze.png",  # fog day
    'clear-night': "assets/Moon.png",  # clear sky night
    'partly-cloudy-night': "assets/PartlyMoon.png",  # scattered clouds night
    'thunderstorm': "assets/Storm.png",  # thunderstorm
    'tornado': "assets/Tornado.png",    # tornado
    'hail': "assets/Hail.png"  # hail
}

METEOSIX_BASE_URL = 'https://servizos.meteogalicia.gal/apiv5'

MG_SKY_DESCRIPTIONS_ES = {
    'SUNNY': 'Despejado',
    'HIGH_CLOUDS': 'Nubes altas',
    'MID_CLOUDS': 'Nubes medias',
    'PARTLY_CLOUDY': 'Parcialmente nublado',
    'CLOUDY': 'Nublado',
    'OVERCAST': 'Cubierto',
    'FOG': 'Niebla',
    'MIST': 'Bruma',
    'FOG_BANK': 'Banco de niebla',
    'SHOWERS': 'Chubascos',
    'WEAK_SHOWERS': 'Chubascos débiles',
    'DRIZZLE': 'Llovizna',
    'RAIN': 'Lluvia',
    'WEAK_RAIN': 'Lluvia débil',
    'OVERCAST_AND_SHOWERS': 'Cubierto con chubascos',
    'SNOW': 'Nieve',
    'INTERMITENT_SNOW': 'Nieve intermitente',
    'MELTED_SNOW': 'Aguanieve',
    'STORMS': 'Tormenta',
    'STORM_THEN_CLOUDY': 'Tormenta, luego nublado',
    'RAIN_HAIL': 'Lluvia con granizo',
}

MG_SKY_DESCRIPTIONS_GL = {
    'SUNNY': 'Despexado',
    'HIGH_CLOUDS': 'Nubes altas',
    'MID_CLOUDS': 'Nubes medias',
    'PARTLY_CLOUDY': 'Parcialmente anubrado',
    'CLOUDY': 'Anubrado',
    'OVERCAST': 'Cubierto',
    'FOG': 'Neboa',
    'MIST': 'Brétema',
    'FOG_BANK': 'Banco de neboa',
    'SHOWERS': 'Chuvascos',
    'WEAK_SHOWERS': 'Chuvascos débiles',
    'DRIZZLE': 'Orballo',
    'RAIN': 'Choiva',
    'WEAK_RAIN': 'Choiva débil',
    'OVERCAST_AND_SHOWERS': 'Cubierto con chuvascos',
    'SNOW': 'Neve',
    'INTERMITENT_SNOW': 'Neve intermitente',
    'MELTED_SNOW': 'Auganeve',
    'STORMS': 'Treboada',
    'STORM_THEN_CLOUDY': 'Treboada, despois anubrado',
    'RAIN_HAIL': 'Choiva con burán',
}


def _mg_sky_descriptions():
    if weather_lang.startswith('es'):
        return MG_SKY_DESCRIPTIONS_ES
    return MG_SKY_DESCRIPTIONS_GL


def _mg_no_data_label():
    return 'Sin datos' if weather_lang.startswith('es') else 'Sen datos'


def _mg_forecast_prefix():
    return 'Próximas horas: %s' if weather_lang.startswith('es') else 'Nas próximas horas: %s'

MG_SKY_TO_ICON = {
    'SUNNY': 'clear-day',
    'HIGH_CLOUDS': 'partly-cloudy-day',
    'MID_CLOUDS': 'partly-cloudy-day',
    'PARTLY_CLOUDY': 'partly-cloudy-day',
    'CLOUDY': 'cloudy',
    'OVERCAST': 'cloudy',
    'FOG': 'fog',
    'MIST': 'fog',
    'FOG_BANK': 'fog',
    'SHOWERS': 'rain',
    'WEAK_SHOWERS': 'rain',
    'DRIZZLE': 'rain',
    'RAIN': 'rain',
    'WEAK_RAIN': 'rain',
    'OVERCAST_AND_SHOWERS': 'rain',
    'SNOW': 'snow',
    'INTERMITENT_SNOW': 'snow',
    'MELTED_SNOW': 'snow',
    'STORMS': 'thunderstorm',
    'STORM_THEN_CLOUDY': 'thunderstorm',
    'RAIN_HAIL': 'hail',
}


def _mg_normalize_sky(code):
    return code.strip().upper().replace('-', '_').replace(' ', '_')


def _mg_parse_time_instant(value):
    if not isinstance(value, str):
        return None
    try:
        if value.endswith('Z'):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _mg_is_daytime(when, sunrise=None, sunset=None):
    if sunrise is not None and sunset is not None:
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return sunrise <= when < sunset
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    hour = when.astimezone().hour
    return 6 <= hour < 21


def _mg_sky_icon_key(code, when, sunrise=None, sunset=None):
    normalized = _mg_normalize_sky(code)
    base = MG_SKY_TO_ICON.get(normalized, 'cloudy')
    is_day = _mg_is_daytime(when, sunrise, sunset)
    if normalized == 'SUNNY' and not is_day:
        return 'clear-night'
    if base == 'partly-cloudy-day' and not is_day:
        return 'partly-cloudy-night'
    return base


def _mg_check_feature(features):
    if not isinstance(features, list) or not features:
        raise ValueError('MeteoGalicia devolveu unha resposta baleira')
    feat = features[0]
    exc = feat.get('exception')
    if isinstance(exc, dict):
        code = exc.get('code')
        message = exc.get('message', 'Erro MeteoGalicia')
        raise ValueError("%s: %s" % (code, message))
    if feat.get('properties') is None:
        raise ValueError(
            'O punto indicado está fóra da área de predición de MeteoGalicia '
            '(só Galicia). Código 216/217.'
        )


def _mg_iter_values_by_variable(data):
    out = {}
    features = data.get('features')
    if not isinstance(features, list) or not features:
        return out
    _mg_check_feature(features)
    props = features[0].get('properties')
    if not isinstance(props, dict):
        return out
    days = props.get('days')
    if not isinstance(days, list):
        return out
    for day in days:
        if not isinstance(day, dict):
            continue
        variables = day.get('variables')
        if not isinstance(variables, list):
            continue
        for var in variables:
            if not isinstance(var, dict):
                continue
            name = var.get('name')
            values = var.get('values')
            if not name or not isinstance(values, list):
                continue
            bucket = out.setdefault(str(name), [])
            for value in values:
                if isinstance(value, dict):
                    bucket.append(value)
    return out


def _mg_pick_nearest(values, now):
    best = None
    best_diff = None
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    for value in values:
        if value.get('value') is None:
            continue
        when = _mg_parse_time_instant(value.get('timeInstant'))
        if when is None:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        diff = abs((when - now).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best = (when, value)
    return best


def _mg_check_api_exception(data):
    if not isinstance(data, dict):
        return
    exc = data.get('exception')
    if not isinstance(exc, dict):
        return
    code = str(exc.get('code', ''))
    message = exc.get('message', 'Erro MeteoGalicia')
    if code in ('005', '006'):
        raise ValueError("API key de MeteoGalicia inválida ou ausente (códigos 005/006).")
    raise ValueError("%s: %s" % (code, message))


def _mg_common_params(lat, lon, lang):
    return {
        'API_KEY': meteogalicia_api_key,
        'coords': '%s,%s' % (lon, lat),
        'lang': lang,
        'tz': 'Europe/Madrid',
        'format': 'application/json',
        'exceptionsFormat': 'application/json',
    }


def _mg_temperature_units():
    # Manual v5: unidades por variable; sky_state sen unidade (cadea baleira).
    temp_unit = 'degF' if weather_unit == 'imperial' else 'degC'
    return '%s,' % temp_unit


def _mg_sunrise_sunset_for_day(solar_data, day):
    features = solar_data.get('features')
    if not isinstance(features, list) or not features:
        return None, None
    feat = features[0]
    if isinstance(feat.get('exception'), dict):
        return None, None
    props = feat.get('properties')
    if not isinstance(props, dict):
        return None, None
    for day_obj in props.get('days') or []:
        begin = _mg_parse_time_instant(
            (day_obj.get('timePeriod') or {}).get('begin', {}).get('timeInstant')
        )
        if begin is None or begin.date() != day:
            continue
        for var in day_obj.get('variables') or []:
            if var.get('name') == 'solar':
                return (
                    _mg_parse_time_instant(var.get('sunrise')),
                    _mg_parse_time_instant(var.get('sunset')),
                )
    return None, None


def _interleave_headlines(sources_entries, total_max):
    """Intercala titulares: 1º de cada medio, 2º de cada medio, etc."""
    if not sources_entries:
        return []
    max_len = max(len(entries) for _, entries in sources_entries)
    merged = []
    for i in range(max_len):
        for source, entries in sources_entries:
            if i < len(entries):
                title = getattr(entries[i], 'title', None)
                if title:
                    merged.append((source, _clean_headline(title)))
                if len(merged) >= total_max:
                    return merged
    return merged


class Clock(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, bg='black')
        # initialize time label
        self.time1 = ''
        self.timeLbl = Label(self, font=('Helvetica', large_text_size), fg="white", bg="black")
        self.timeLbl.pack(side=TOP, anchor=E)
        # initialize day of week
        self.day_of_week1 = ''
        self.dayOWLbl = Label(self, text=self.day_of_week1, font=('Helvetica', medium_text_size), fg="white", bg="black")
        self.dayOWLbl.pack(side=TOP, anchor=E)
        # initialize date label
        self.date1 = ''
        self.dateLbl = Label(self, text=self.date1, font=('Helvetica', medium_text_size), fg="white", bg="black")
        self.dateLbl.pack(side=TOP, anchor=E)
        self.tick()

    def tick(self):
        with setlocale(ui_locale):
            time2 = time.strftime('%H:%M')

            day_of_week2 = time.strftime('%A')
            date2 = time.strftime(date_format)
            # if time string has changed, update it
            if time2 != self.time1:
                self.time1 = time2
                self.timeLbl.config(text=time2)
            if day_of_week2 != self.day_of_week1:
                self.day_of_week1 = day_of_week2
                self.dayOWLbl.config(text=day_of_week2)
            if date2 != self.date1:
                self.date1 = date2
                self.dateLbl.config(text=date2)
            # calls itself every 200 milliseconds
            # to update the time display as needed
            # could use >200 ms, but display gets jerky
            self.timeLbl.after(200, self.tick)


class Weather(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, bg='black')
        self.temperature = ''
        self.forecast = ''
        self.location = ''
        self.currently = ''
        self.icon = ''
        self.degreeFrm = Frame(self, bg="black")
        self.degreeFrm.pack(side=TOP, anchor=W)
        self.temperatureLbl = Label(self.degreeFrm, font=('Helvetica', xlarge_text_size), fg="white", bg="black")
        self.temperatureLbl.pack(side=LEFT, anchor=N)
        self.iconLbl = Label(self.degreeFrm, bg="black")
        self.iconLbl.pack(side=LEFT, anchor=N, padx=20)
        self.currentlyLbl = Label(self, font=('Helvetica', small_text_size), fg="white", bg="black")
        self.currentlyLbl.pack(side=TOP, anchor=W)
        self.forecastLbl = Label(self, font=('Helvetica', small_text_size), fg="white", bg="black")
        self.forecastLbl.pack(side=TOP, anchor=W)
        self.locationLbl = Label(self, font=('Helvetica', small_text_size), fg="white", bg="black")
        self.locationLbl.pack(side=TOP, anchor=W)
        self._fetch_retries = 0
        self.after(startup_fetch_delay_ms, self.get_weather)

    def _resolve_coords(self):
        if location_name:
            location2 = location_name
        else:
            location2 = None

        if latitude is None and longitude is None:
            geo_resp = requests.get("http://ip-api.com/json/", timeout=10)
            geo_resp.raise_for_status()
            location_obj = geo_resp.json()
            if location_obj.get('status') != 'success':
                raise ValueError(location_obj.get('message', 'Non se puido obter a ubicación'))
            lat = location_obj['lat']
            lon = location_obj['lon']
            if not location2:
                location2 = "%s, %s" % (location_obj.get('city', ''), location_obj.get('regionName', ''))
        else:
            lat = float(latitude)
            lon = float(longitude)

        if not location2:
            location2 = self._reverse_geocode(lat, lon)

        return lat, lon, location2

    def _reverse_geocode(self, lat, lon):
        resp = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'lat': lat, 'lon': lon, 'format': 'json', 'accept-language': 'gl,es'},
            headers={'User-Agent': 'smart-mirror/1.0'},
            timeout=10,
        )
        resp.raise_for_status()
        address = resp.json().get('address', {})
        for key in ('city', 'town', 'village', 'municipality', 'county'):
            if address.get(key):
                return address[key]
        display = resp.json().get('display_name', '')
        return display.split(',')[0] if display else ''

    def _fetch_meteogalicia(self, lat, lon):
        if not meteogalicia_api_key:
            raise ValueError("Falta a chave API de MeteoGalicia (MeteoSIX).")

        lang = 'es' if weather_lang.startswith('es') else weather_lang
        common = _mg_common_params(lat, lon, lang)

        forecast_resp = requests.get(
            '%s/getNumericForecastInfo' % METEOSIX_BASE_URL,
            params=dict(common, **{
                'variables': 'temperature,sky_state',
                'units': _mg_temperature_units(),
            }),
            timeout=15,
        )
        forecast_resp.raise_for_status()
        data = forecast_resp.json()
        _mg_check_api_exception(data)

        solar_resp = requests.get(
            '%s/getSolarInfo' % METEOSIX_BASE_URL,
            params=common,
            timeout=15,
        )
        solar_resp.raise_for_status()
        solar_data = solar_resp.json()
        _mg_check_api_exception(solar_data)

        by_var = _mg_iter_values_by_variable(data)
        now = datetime.now(timezone.utc)

        temps = by_var.get('temperature', [])
        skies = by_var.get('sky_state', [])
        nearest_temp = _mg_pick_nearest(temps, now)
        if nearest_temp is None:
            raise ValueError('MeteoGalicia non devolveu temperatura para estas coordenadas')

        slot_dt, temp_value = nearest_temp
        temp = temp_value.get('value')
        if temp is None:
            raise ValueError('MeteoGalicia non devolveu temperatura válida')

        degree_sign = '\N{DEGREE SIGN}'
        temperature2 = "%s%s" % (int(round(float(temp))), degree_sign)

        local_day = slot_dt.astimezone().date()
        sunrise, sunset = _mg_sunrise_sunset_for_day(solar_data, local_day)

        sky_by_dt = {}
        for sky_value in skies:
            when = _mg_parse_time_instant(sky_value.get('timeInstant'))
            if when is not None:
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                sky_by_dt[when] = sky_value

        sky_value = sky_by_dt.get(slot_dt)
        if sky_value is None:
            nearest_sky = _mg_pick_nearest(skies, now)
            sky_value = nearest_sky[1] if nearest_sky else None

        sky_descriptions = _mg_sky_descriptions()
        sky_code = sky_value.get('value') if isinstance(sky_value, dict) else None
        if isinstance(sky_code, str):
            normalized = _mg_normalize_sky(sky_code)
            currently2 = sky_descriptions.get(normalized, sky_code.replace('_', ' ').title())
            icon2 = icon_lookup.get(_mg_sky_icon_key(sky_code, slot_dt, sunrise, sunset))
        else:
            currently2 = _mg_no_data_label()
            icon2 = None

        future_skies = sorted(
            ((when, item) for when, item in sky_by_dt.items() if when > slot_dt),
            key=lambda pair: pair[0],
        )
        if future_skies:
            next_code = future_skies[0][1].get('value')
            if isinstance(next_code, str):
                normalized = _mg_normalize_sky(next_code)
                forecast2 = _mg_forecast_prefix() % sky_descriptions.get(
                    normalized, next_code.replace('_', ' ').title()
                )
            else:
                forecast2 = ''
        else:
            forecast2 = ''

        return temperature2, currently2, forecast2, icon2

    def _retry_weather(self, reason):
        if self._fetch_retries < startup_retry_max:
            self._fetch_retries += 1
            _log('Tempo: %s (reintento %d/%d)' % (reason, self._fetch_retries, startup_retry_max))
            self.after(startup_retry_interval_ms, self.get_weather)
            return
        _log('Tempo: sen datos tras %d reintentos' % startup_retry_max)
        self.after(data_refresh_interval_ms, self.get_weather)

    def get_weather(self):
        if not _network_ready():
            self._retry_weather('rede non dispoñible')
            return
        ok = False
        try:
            lat, lon, location2 = self._resolve_coords()
            temperature2, currently2, forecast2, icon2 = self._fetch_meteogalicia(lat, lon)
            ok = True

            if icon2 is not None:
                if self.icon != icon2:
                    self.icon = icon2
                    image = Image.open(icon2)
                    image = image.resize((90, 90), Image.LANCZOS)
                    image = image.convert('RGB')
                    photo = ImageTk.PhotoImage(image)

                    self.iconLbl.config(image=photo)
                    self.iconLbl.image = photo
            else:
                # remove image
                self.iconLbl.config(image='')

            if self.currently != currently2:
                self.currently = currently2
                self.currentlyLbl.config(text=currently2)
            if self.forecast != forecast2:
                self.forecast = forecast2
                self.forecastLbl.config(text=forecast2)
            if self.temperature != temperature2:
                self.temperature = temperature2
                self.temperatureLbl.config(text=temperature2)
            if self.location != location2:
                if location2 == ", ":
                    self.location = "Non se puido determinar a ubicación"
                    self.locationLbl.config(text="Non se puido determinar a ubicación")
                else:
                    self.location = location2
                    self.locationLbl.config(text=location2)
        except Exception as e:
            traceback.print_exc()
            _log("Erro tempo: %s" % e)

        if not ok:
            self._retry_weather('fallo ao obter datos')
            return
        _log('Tempo: datos cargados')
        self._fetch_retries = 0
        self.after(data_refresh_interval_ms, self.get_weather)


class News(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, *args, **kwargs)
        self.config(bg='black')
        self.title = 'Noticias'
        self.newsLbl = Label(self, text=self.title, font=('Helvetica', medium_text_size), fg="white", bg="black")
        self.newsLbl.pack(side=TOP, anchor=W)
        self.headlinesContainer = Frame(self, bg="black")
        self.headlinesContainer.pack(side=TOP)
        self._fetch_retries = 0
        self.after(startup_fetch_delay_ms, self.get_headlines)

    def _retry_headlines(self, reason):
        if self._fetch_retries < startup_retry_max:
            self._fetch_retries += 1
            _log('Noticias: %s (reintento %d/%d)' % (reason, self._fetch_retries, startup_retry_max))
            self.after(startup_retry_interval_ms, self.get_headlines)
            return
        _log('Noticias: sen titulares tras %d reintentos' % startup_retry_max)
        self.after(data_refresh_interval_ms, self.get_headlines)

    def get_headlines(self):
        if not _network_ready():
            self._retry_headlines('rede non dispoñible')
            return
        try:
            for widget in self.headlinesContainer.winfo_children():
                widget.destroy()

            sources_entries = []
            for source, url in news_feeds:
                try:
                    feed = _fetch_rss(url)
                    entries = list(feed.entries[:news_headlines_per_feed])
                    if entries:
                        sources_entries.append((source, entries))
                except Exception as e:
                    traceback.print_exc()
                    _log("Erro feed %s (%s): %s" % (source, url, e))

            headlines = _interleave_headlines(sources_entries, news_headlines_total)
            for source, title in headlines:
                headline = NewsHeadline(self.headlinesContainer, title, source=source)
                headline.pack(side=TOP, anchor=W)

            if not headlines:
                self._retry_headlines('feeds baleiros ou sen rede')
                return
            _log('Noticias: %d titulares cargados' % len(headlines))
        except Exception as e:
            traceback.print_exc()
            _log("Erro noticias: %s" % e)
            self._retry_headlines('excepción')
            return

        self._fetch_retries = 0
        self.after(data_refresh_interval_ms, self.get_headlines)


class NewsHeadline(Frame):
    def __init__(self, parent, event_name="", source=""):
        Frame.__init__(self, parent, bg='black')

        image = Image.open("assets/Newspaper.png")
        image = image.resize((25, 25), Image.LANCZOS)
        image = image.convert('RGB')
        photo = ImageTk.PhotoImage(image)

        self.iconLbl = Label(self, bg='black', image=photo)
        self.iconLbl.image = photo
        self.iconLbl.pack(side=LEFT, anchor=N)

        if source:
            self.eventName = "%s · %s" % (source, event_name)
        else:
            self.eventName = event_name
        self.eventNameLbl = Label(self, text=self.eventName, font=('Helvetica', small_text_size), fg="white", bg="black")
        self.eventNameLbl.pack(side=LEFT, anchor=N)


class Calendar(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, bg='black')
        self.title = 'Eventos do calendario'
        self.calendarLbl = Label(self, text=self.title, font=('Helvetica', medium_text_size), fg="white", bg="black")
        self.calendarLbl.pack(side=TOP, anchor=E)
        self.calendarEventContainer = Frame(self, bg='black')
        self.calendarEventContainer.pack(side=TOP, anchor=E)
        self.get_events()

    def get_events(self):
        for widget in self.calendarEventContainer.winfo_children():
            widget.destroy()

        calendar_event = CalendarEvent(self.calendarEventContainer)
        calendar_event.pack(side=TOP, anchor=E)
        pass


class CalendarEvent(Frame):
    def __init__(self, parent, event_name="Evento 1"):
        Frame.__init__(self, parent, bg='black')
        self.eventName = event_name
        self.eventNameLbl = Label(self, text=self.eventName, font=('Helvetica', small_text_size), fg="white", bg="black")
        self.eventNameLbl.pack(side=TOP, anchor=E)


class FullscreenWindow:

    def __init__(self):
        self.tk = Tk()
        self.tk.configure(background='black')
        self.topFrame = Frame(self.tk, background = 'black')
        self.bottomFrame = Frame(self.tk, background = 'black')
        self.topFrame.pack(side = TOP, fill=BOTH, expand = YES)
        self.bottomFrame.pack(side = BOTTOM, fill=BOTH, expand = YES)
        self.state = False
        self.tk.bind("<Return>", self.toggle_fullscreen)
        self.tk.bind("<Escape>", self.end_fullscreen)
        self.clock = Clock(self.topFrame)
        self.clock.pack(side=RIGHT, anchor=N, padx=100, pady=60)
        self.weather = Weather(self.topFrame)
        self.weather.pack(side=LEFT, anchor=N, padx=100, pady=60)
        self.news = News(self.bottomFrame)
        self.news.pack(side=LEFT, anchor=S, padx=100, pady=60)
        if start_fullscreen:
            self.tk.after(200, self.enter_fullscreen)

    def enter_fullscreen(self, event=None):
        self.state = True
        self.tk.attributes("-fullscreen", True)
        return "break"

    def toggle_fullscreen(self, event=None):
        self.state = not self.state  # Just toggling the boolean
        self.tk.attributes("-fullscreen", self.state)
        return "break"

    def end_fullscreen(self, event=None):
        self.state = False
        self.tk.attributes("-fullscreen", False)
        return "break"

if __name__ == '__main__':
    _log('Smart Mirror iniciado (cwd=%s)' % os.getcwd())
    w = FullscreenWindow()
    w.tk.mainloop()
