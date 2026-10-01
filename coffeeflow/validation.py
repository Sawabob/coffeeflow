"""Перевірки JSON: невідомі поля відхиляються, bool не є цілим числом."""
from datetime import datetime, timezone, timedelta
import re
from urllib.parse import urlsplit
from flask import current_app, request
from .errors import APIError


def fail(field, message):
    raise APIError('validation_error', 'Перевірте вхідні дані.', fields={field: message})


def body(allowed, required=()):
    if not request.is_json:
        raise APIError('unsupported_media_type', 'Потрібен application/json.', 415)
    data = request.get_json()
    return check_object(data, allowed, required)


def check_object(data, allowed, required=()):
    if not isinstance(data, dict):
        fail('body', "Очікується JSON-об'єкт.")
    extra, missing = set(data) - set(allowed), set(required) - set(data)
    if extra:
        fail('body', 'Невідомі поля: ' + ', '.join(sorted(extra)))
    if missing:
        fail('body', 'Обов’язкові поля: ' + ', '.join(sorted(missing)))
    return data


def string(value, field, minimum=1, maximum=80):
    if not isinstance(value, str):
        fail(field, 'Очікується рядок.')
    value = value.strip()
    if not minimum <= len(value) <= maximum or any(ord(c) < 32 for c in value):
        fail(field, f'Довжина {minimum}–{maximum}, без керівних символів.')
    return value


def integer(value, field, minimum=1, maximum=2147483647):
    if type(value) is not int or not minimum <= value <= maximum:
        fail(field, f'Потрібне ціле число {minimum}–{maximum}.')
    return value


def boolean(value, field):
    if type(value) is not bool:
        fail(field, 'Потрібне true або false.')
    return value


def pagination(allowed_extra=()):
    allowed = {'limit', 'offset', *allowed_extra}
    if set(request.args) - allowed:
        fail('query', 'Невідомі параметри запиту.')
    for key in request.args:
        if len(request.args.getlist(key)) != 1:
            fail(key, 'Повторений параметр.')
    def parse(key, default, minimum, maximum):
        raw = request.args.get(key, str(default))
        if not re.fullmatch(r'[0-9]{1,10}', raw):
            fail(key, 'Потрібне ціле невід’ємне число.')
        return integer(int(raw), key, minimum, maximum)
    return parse('limit', 20, 1, 100), parse('offset', 0, 0, 1000000)


def product_fields(data):
    result = {}
    for key, val in data.items():
        if key == 'category_id':
            val = integer(val, key)
        elif key == 'price_cents':
            val = integer(val, key, 1, 10000000)
        elif key == 'is_available':
            val = boolean(val, key)
        elif key in ('name', 'description'):
            val = string(val, key, 1 if key == 'name' else 0,
                         120 if key == 'name' else 2000)
        elif key == 'image_url':
            val = string(val, key, 0, 500)
            try:
                url = urlsplit(val)
                valid = url.scheme == 'https' and bool(url.hostname) and not url.username
                valid = valid and not any(c.isspace() for c in url.netloc)
                _ = url.port
            except ValueError:
                valid = False
            if val and not valid:
                fail(key, 'Потрібен HTTPS URL без облікових даних або порожній рядок.')
        result[key] = val
    return result


def utc_now():
    return current_app.config['NOW']().astimezone(timezone.utc)


def pickup_time(raw):
    raw = string(raw, 'pickup_at', 20, 40)
    try:
        result = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        fail('pickup_at', 'Потрібна дата ISO 8601 із часовим поясом.')
    if result.tzinfo is None:
        fail('pickup_at', 'Вкажіть часовий пояс.')
    try:
        result = result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        fail('pickup_at', 'Дата поза підтримуваним діапазоном.')
    now = utc_now()
    if not now + timedelta(minutes=15) <= result <= now + timedelta(days=7):
        fail('pickup_at', 'Час отримання: від 15 хвилин до 7 днів від поточного часу.')
    return result.isoformat()


def order_fields(data):
    name = string(data['customer_name'], 'customer_name', 2, 80)
    phone = string(data['phone'], 'phone', 9, 16)
    if not re.fullmatch(r'\+[1-9][0-9]{7,14}', phone):
        fail('phone', 'Міжнародний формат: + та 8–15 цифр.')
    pickup = pickup_time(data['pickup_at'])
    comment = string(data.get('comment', ''), 'comment', 0, 500)
    items = data['items']
    if not isinstance(items, list) or not 1 <= len(items) <= 30:
        fail('items', 'Потрібно від 1 до 30 позицій.')
    parsed, seen = [], set()
    for item in items:
        check_object(item, {'product_id', 'quantity'}, {'product_id', 'quantity'})
        product_id = integer(item['product_id'], 'product_id')
        quantity = integer(item['quantity'], 'quantity', 1, 20)
        if product_id in seen:
            fail('items', 'Об’єднайте повторені товари в одну позицію.')
        seen.add(product_id)
        parsed.append((product_id, quantity))
    return name, phone, pickup, comment, parsed
