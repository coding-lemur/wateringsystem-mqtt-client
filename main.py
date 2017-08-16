import argparse
import json
import logging
import logging.config
import os

import paho.mqtt.client as mqtt
import yaml

from services.data_service import DataService
from services.watering_service import WateringService
from services.config_service import ConfigService


def load_args():
    # setup commandline argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('--env')

    return parser.parse_args()


def setup_logging(default_level=logging.INFO):
    path = os.path.join(os.getcwd(), 'config', 'logging.yml')

    if os.path.exists(path):
        # load from config
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


def create_mqtt_client(config):
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set(config['user'], config['password'])
    client.connect(config['host'], config['port'])

    return client


def watering(sensors_id, milliseconds):
    mqtt_client.publish(watering_config['topic'], milliseconds)
    data_service.save_watering(sensors_id, milliseconds)


def on_connect(client, userdata, flags_dict, rc):
    if rc != 0:
        logger.error('MQTT connection error: ' + str(rc))
        return

    logger.info('MQTT connected')

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(mqtt_config['topic'])


def on_message(client, userdata, msg):
    logger.info('receive message "%s": %s', msg.topic, str(msg.payload))

    # transform payload to JSON
    sensor_values = json.loads(msg.payload.decode('utf-8'))

    temperature = sensor_values['Temperature']
    humidity = sensor_values['Humidity']
    soil_moisture = sensor_values['SoilMoisture']

    sensors_id = data_service.save_sensor_values(temperature, humidity, soil_moisture)

    if sensors_id is not None:
        watering_milliseconds = watering_service.calculate_milliseconds(soil_moisture)

        if watering_milliseconds > 200:
            watering(sensors_id, watering_milliseconds)


args = load_args()
setup_logging()
logger = logging.getLogger(__name__)

logger.info('starting MQTT client')

try:
    config_service = ConfigService(args.env)
    mqtt_config = config_service.get_section('mqtt')
    mysql_config = config_service.get_section('mysql')
    watering_config = config_service.get_section('watering')

    data_service = DataService(mysql_config)
    watering_service = WateringService(watering_config)

    mqtt_client = create_mqtt_client(mqtt_config)
    mqtt_client.loop_forever()
except Exception as error:
    logger.error('main error', exc_info=True)
