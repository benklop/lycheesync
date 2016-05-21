# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import unicode_literals

import datetime
import decimal
import hashlib
import logging
import math
import mimetypes
import os
import random
import time
from fractions import Fraction

import pyexiv2
from dateutil.parser import parse

logger = logging.getLogger(__name__)


class ExifData:

    """
    Use to store ExifData
    """

    @property
    def takedate(self):
        return self._takedate

    @takedate.setter
    def takedate(self, value):
        self._takedate = value.replace(':', '-')

    iso = ""
    make = ""
    model = ""
    shutter = None
    aperture = None
    exposure = None
    focal = None
    _takedate = None
    taketime = None
    orientation = 1

    def __str__(self):
        res = ""
        res += "iso: " + str(self.iso) + "\n"
        res += "aperture: " + str(self.aperture) + "\n"
        res += "make: " + str(self.make) + "\n"
        res += "model: " + str(self.model) + "\n"
        res += "shutter: " + str(self.shutter) + "\n"
        res += "exposure: " + str(self.exposure) + "\n"
        res += "focal: " + str(self.focal) + "\n"
        res += "takedate: " + str(self.takedate) + "\n"
        res += "taketime: " + str(self.taketime) + "\n"
        res += "orientation: " + str(self.orientation) + "\n"
        return res


class LycheePhoto:

    """
    Use to store photo data
    """

    originalname = ""  # import_name
    originalpath = ""
    id = ""
    albumname = ""
    albumid = ""
    thumbnailfullpath = ""
    thumbnailx2fullpath = ""
    title = ""
    description = ""
    url = ""
    public = 0  # private by default
    type = ""
    width = 0
    height = 0
    size = ""
    star = 0  # no star by default
    thumbUrl = ""
    srcfullpath = ""
    destfullpath = ""
    tags = ""
    exif = None
    _str_datetime = None
    checksum = ""

    def convert_strdate_to_timestamp(self, value):
        # check parameter type
        # logger.debug("convert_strdate input: " + str(value))
        # logger.debug("convert_strdate input_type: " + str(type(value)))

        timestamp = None
        # now in epoch time
        epoch_now = int(time.time())
        timestamp = epoch_now

        if isinstance(value, int):
            timestamp = value
        elif isinstance(value, datetime.date):
            timestamp = (value - datetime.datetime(1970, 1, 1)).total_seconds()
        elif value:

            value = str(value)

            try:
                the_date = parse(value)
                # works for python 3
                # timestamp = the_date.timestamp()
                timestamp = time.mktime(the_date.timetuple())

            except Exception as e:
                logger.warn('model date impossible to parse: ' + str(value))
                timestamp = epoch_now
        else:
            # Value is None
            timestamp = epoch_now

        return timestamp

    @property
    def epoch_sysdate(self):
        return self.convert_strdate_to_timestamp(self._str_datetime)

    # Compute checksum
    def __generateHash(self):
        sha1 = hashlib.sha1()
        with open(self.srcfullpath, 'rb') as f:
            sha1.update(f.read())
            self.checksum = sha1.hexdigest()

    def __init__(self, conf, photoname, album):
        # Parameters storage
        self.conf = conf
        self.originalname = photoname
        self.originalpath = album['path']
        self.albumid = album['id']
        self.albumname = album['name']

        # if star in file name, photo is starred
        if ('star' in self.originalname) or ('cover' in self.originalname):
            self.star = 1

        # Compute Photo ID
        self.id = str(int(time.time()))
        # not precise enough
        length = len(self.id)
        if length < 14:
            missing_char = 14 - length
            r = random.random()
            r = str(r)
            # last missing_char char
            filler = r[-missing_char:]
            self.id = self.id + filler

        assert len(self.id) == 14, "id {} is not 14 character long: {}".format(self.id, str(len(self.id)))

        # Compute file storage url
        m = hashlib.md5()
        m.update(self.id.encode('utf-8'))
        crypted = m.hexdigest()

        ext = os.path.splitext(photoname)[1]
        self.url = ''.join([crypted, ext]).lower()
        self.thumbUrl = self.url

        # src and dest fullpath
        self.srcfullpath = os.path.join(self.originalpath, self.originalname)
        self.destfullpath = os.path.join(self.conf["lycheepath"], "uploads", "big", self.url)

        # Generate file checksum
        self.__generateHash()

        # thumbnails already in place (see makeThumbnail)

        # Auto file some properties
        self.type = mimetypes.guess_type(self.originalname, False)[0]
        self.size = os.path.getsize(self.srcfullpath)
        self.size = str(self.size / 1024) + " KB"
        # Default date
        takedate = datetime.date.today().isoformat()
        taketime = datetime.datetime.now().strftime('%H:%M:%S')
        self._str_datetime = takedate + " " + taketime

        # Exif Data Parsing
        self.exif = ExifData()
        try:

            metadata = pyexiv2.ImageMetadata(self.srcfullpath)

            metadata.read()
            w = metadata['Exif.Photo.PixelXDimension'].value
            h = metadata['Exif.Photo.PixelYDimension'].value

            self.width = float(w)
            self.height = float(h)

            # exifinfo = img.info['exif']
            # logger.debug(exifinfo)

            if "Exif.Image.Orientation" in metadata.exif_keys:
                self.exif.orientation = metadata['Exif.Image.Orientation'].value
            if "Exif.Image.Make" in metadata.exif_keys:
                self.exif.make = metadata['Exif.Image.Make'].value
            if "Exif.Photo.MaxApertureValue" in metadata.exif_keys:
                aperture = math.sqrt(2) ** metadata['Exif.Photo.MaxApertureValue'].value
                try:
                    aperture = decimal.Decimal(aperture).quantize(
                        decimal.Decimal('.1'),
                        rounding=decimal.ROUND_05UP)
                except Exception as e:
                    logger.debug("aperture only a few digit after comma: {}".format(aperture))
                    logger.debug(e)
                self.exif.aperture = aperture
            if "Exif.Photo.FocalLength" in metadata.exif_keys:
                focal = metadata['Exif.Photo.FocalLength'].value * 1.0
                self.exif.focal = decimal.Decimal(focal).quantize(decimal.Decimal('0.1'), rounding=decimal.ROUND_05UP)
            if "Exif.Photo.ISOSpeedRatings" in metadata.exif_keys:
                self.exif.iso = metadata['Exif.Photo.ISOSpeedRatings'].value
            if "Exif.Photo.Model" in metadata.exif_keys:
                self.exif.model = metadata['Exif.Image.Model'].value
            if "Exif.Photo.ExposureTime" in metadata.exif_keys:
                self.exif.exposure = metadata['Exif.Photo.ExposureTime'].value
            if "Exif.Photo.ExposureTime" in metadata.exif_keys:
                s = metadata['Exif.Photo.ExposureTime'].value
                s = Fraction(int(decimal.Decimal(s.numerator / 10).quantize(decimal.Decimal('1'),
                                                                            rounding=decimal.ROUND_HALF_EVEN))
                             , int(decimal.Decimal(s.denominator / 10).quantize(decimal.Decimal('1'),
                                                                                rounding=decimal.ROUND_HALF_EVEN)))
                self.exif.shutter = str(s) + " s"
            if "Exif.Photo.DateTimeOriginal" in metadata.exif_keys:
                try:
                    self.exif.takedate = metadata['Exif.Photo.DateTimeOriginal'].raw_value.split(" ")[0]
                except Exception as e:
                    logger.warn('invalid takedate: ' + str(
                        metadata['Exif.Photo.DateTimeOriginal'].raw_value) + ' for ' + self.srcfullpath)
            if "Exif.Photo.DateTimeOriginal" in metadata.exif_keys:
                try:
                    self.exif.taketime = metadata['Exif.Photo.DateTimeOriginal'].raw_value.split(" ")[1]
                except Exception as e:
                    logger.warn('invalid taketime: ' + str(
                        metadata['Exif.Photo.DateTimeOriginal'].raw_value) + ' for ' + self.srcfullpath)

            if "Exif.Photo.DateTime" in metadata.exif_keys and self.exif.takedate is None:
                try:
                    self.exif.takedate = metadata['Exif.Photo.DateTime'].raw_value.split(" ")[0]
                except Exception as e:
                    logger.warn('DT invalid takedate: ' + str(
                        metadata['Exif.Photo.DateTime'].raw_value) + ' for ' + self.srcfullpath)

            if "Exif.Photo.DateTime" in metadata.exif_keys and self.exif.taketime is None:
                try:
                    self.exif.taketime = metadata['Exif.Photo.DateTime'].raw_value.split(" ")[1]
                except Exception as e:
                    logger.warn('DT invalid taketime: ' + str(
                        metadata['Exif.Photo.DateTime'].raw_value) + ' for ' + self.srcfullpath)
            if "Iptc.Application2.ObjectName" in metadata.iptc_keys:
                self.title = metadata['Iptc.Application2.ObjectName'].value or self.originalname
            if "Xmp.xmp.Rating" in metadata.xmp_keys:
                self.star = metadata['Xmp.xmp.Rating'].value or "0"
            if "Iptc.Application2.Caption" in metadata.iptc_keys:
                self.description = metadata['Iptc.Application2.Caption'].value or ""
            if "Iptc.Application2.Keywords" in metadata.iptc_keys:
                tags = metadata['Iptc.Application2.Keywords'].value or {""}
                self.tags = ','.join(tags)
            # compute shutter speed

            if not (self.exif.shutter) and self.exif.exposure:
                if self.exif.exposure < 1:
                    e = str(Fraction(self.exif.exposure).limit_denominator())
                else:
                    e = decimal.Decimal(
                        self.exif.exposure).quantize(
                        decimal.Decimal('0.01'),
                        rounding=decimal.ROUND_05UP)
                self.exif.shutter = e

            if self.exif.shutter:
                self.exif.shutter = str(self.exif.shutter) + " s"
            else:
                self.exif.shutter = ""

            if self.exif.exposure:
                self.exif.exposure = str(self.exif.exposure) + " s"
            else:
                self.exif.exposure = ""

            if self.exif.focal:
                self.exif.focal = str(self.exif.focal) + " mm"
            else:
                self.exif.focal = ""

            if self.exif.aperture:
                self.exif.aperture = 'F' + str(self.exif.aperture)
            else:
                self.exif.aperture = ""

            # compute takedate / taketime
            if self.exif.takedate:
                takedate = self.exif.takedate.replace(':', '-')
                self.exif.takedate = takedate
                taketime = '00:00:00'

            if self.exif.taketime:
                taketime = self.exif.taketime

            # add mesurement units

            self._str_datetime = takedate + " " + taketime


        except IOError as e:
            logger.debug('ioerror (corrupted ?): ' + self.srcfullpath)
            raise e

    def __str__(self):
        res = ""
        res += "originalname:" + str(self.originalname) + "\n"
        res += "originalpath:" + str(self.originalpath) + "\n"
        res += "id:" + str(self.id) + "\n"
        res += "albumname:" + str(self.albumname) + "\n"
        res += "albumid:" + str(self.albumid) + "\n"
        res += "thumbnailfullpath:" + str(self.thumbnailfullpath) + "\n"
        res += "thumbnailx2fullpath:" + str(self.thumbnailx2fullpath) + "\n"
        res += "title:" + str(self.title) + "\n"
        res += "description:" + str(self.description) + "\n"
        res += "url:" + str(self.url) + "\n"
        res += "public:" + str(self.public) + "\n"
        res += "type:" + str(self.type) + "\n"
        res += "width:" + str(self.width) + "\n"
        res += "height:" + str(self.height) + "\n"
        res += "size:" + str(self.size) + "\n"
        res += "star:" + str(self.star) + "\n"
        res += "thumbUrl:" + str(self.thumbUrl) + "\n"
        res += "srcfullpath:" + str(self.srcfullpath) + "\n"
        res += "destfullpath:" + str(self.destfullpath) + "\n"
        res += "_str_datetime:" + self._str_datetime + "\n"
        res += "epoch_sysdate:" + str(self.epoch_sysdate) + "\n"
        res += "checksum:" + self.checksum + "\n"
        res += "Exif: \n" + str(self.exif) + "\n"
        return res
