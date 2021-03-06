# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import unicode_literals

import datetime
import logging
import re

import pymysql
from dateutil.parser import parse

logger = logging.getLogger(__name__)


class LycheeDAO:
    """
    Implements linking with Lychee DB
    """

    db = None
    db2 = None
    conf = None
    albumslist = {}

    def __init__(self, conf):
        """
        Takes a dictionnary of conf as input
        """
        try:
            self.conf = conf
            if 'dbSocket' in self.conf:
                logger.debug("Connection to db in SOCKET mode")
                logger.debug("host: %s", self.conf['dbHost'])
                logger.debug("user: %s", self.conf['dbUser'])
                logger.debug("password: %s", self.conf['dbPassword'])
                logger.debug("db: %s", self.conf['db'])
                logger.debug("unix_socket: %s", self.conf['dbSocket'])
                self.db = pymysql.connect(host=self.conf['dbHost'],
                                          user=self.conf['dbUser'],
                                          passwd=self.conf['dbPassword'],
                                          db=self.conf['db'],
                                          charset='utf8mb4',
                                          unix_socket=self.conf['dbSocket'],
                                          cursorclass=pymysql.cursors.DictCursor)
            else:
                logger.debug("Connection to db in NO SOCKET mode")
                self.db = pymysql.connect(host=self.conf['dbHost'],
                                          user=self.conf['dbUser'],
                                          passwd=self.conf['dbPassword'],
                                          db=self.conf['db'],
                                          charset='utf8mb4',
                                          cursorclass=pymysql.cursors.DictCursor)

            cur = self.db.cursor()
            cur.execute("set names utf8;")

            if self.conf["dropdb"]:
                self.dropAll()

            self.loadAlbumList()

        except Exception as e:
            logger.error(e)
            raise

    def getAlbumNameDBWidth(self):
        res = 50  # default value
        query = "show columns from lychee_albums where Field='title'"
        cur = self.db.cursor()
        try:
            cur.execute(query)
            row = cur.fetchone()
            type = row['Type']
            # is type ok
            p = re.compile('varchar\(\d+\)', re.IGNORECASE)
            if p.match(type):
                # remove varchar(and)
                p = re.compile('\d+', re.IGNORECASE)
                ints = p.findall(type)
                if len(ints) > 0:
                    res = int(ints[0])
            else:
                logger.warn("getAlbumNameDBWidth unable to find album name width fallback to default")
        except Exception as e:
            logger.exception(e)
            logger.warn("getAlbumNameDBWidth while executing: " + cur._last_executed)
        finally:
            return res

    def getAlbumMinMaxIds(self):
        """
        returns min, max album ids
        """
        min_album_query = "select min(id) as min from lychee_albums"
        max_album_query = "select max(id) as max from lychee_albums"
        try:
            cur = self.db.cursor()

            cur.execute(min_album_query)
            rows = cur.fetchone()
            min = rows['min']

            cur.execute(max_album_query)
            rows = cur.fetchone()
            max = rows['max']

            if min is None:
                min = -1

            if max is None:
                max = -1

            logger.debug("min max album id: %s to %s", min, max)

            res = min, max
        except Exception as e:
            res = -1, -1
            logger.error("getAlbumMinMaxIds default id defined")
            logger.exception(e)
        finally:
            return res

    def updateAlbumDate(self, albumid, newdate):
        """
        Update album date to an arbitrary date
        newdate is an epoch timestamp
        """

        res = True
        try:
            qry = "update lychee_albums set sysstamp= '" + str(newdate) + "' where id=" + str(albumid)
            cur = self.db.cursor()
            cur.execute(qry)
            self.db.commit()
        except Exception as e:
            logger.exception(e)
            res = False
            logger.error("updateAlbumDate", Exception)
            raise
        finally:
            return res

    def changeAlbumId(self, oldid, newid):
        """
        Change albums id based on album titles (to affect display order)
        """
        res = True
        photo_query = "update lychee_photos set album = " + str(newid) + " where album = " + str(oldid)
        album_query = "update lychee_albums set id = " + str(newid) + " where id = " + str(oldid)
        try:
            cur = self.db.cursor()
            cur.execute(photo_query)
            cur.execute(album_query)
            self.db.commit()
            logger.debug("album id changed: " + str(oldid) + " to " + str(newid))
        except Exception as e:
            logger.exception(e)
            logger.error("album id changed: " + str(oldid) + " to " + str(newid))
            res = False
        finally:
            return res

    def loadAlbumList(self):
        """
        retrieve all albums in a dictionnary key=title value=id
        and put them in self.albumslist
        returns self.albumlist
        """
        # Load album list
        cur = self.db.cursor()
        cur.execute("SELECT title,id from lychee_albums")
        rows = cur.fetchall()
        for row in rows:
            self.albumslist[row['title']] = row['id']

        logger.debug("album list in db:" + str(self.albumslist))
        return self.albumslist

    def albumIdExists(self, album_id):
        res = False
        try:
            cur = self.db.cursor()
            cur.execute("select * from lychee_albums where id=%s", (album_id))
            row = cur.fetchall()
            if len(row) != 0:
                res = True
        except Exception as e:
            logger.exception(e)
        finally:
            return res

    def albumExistsByNameAndParent(self, album_name, parent):
        res = False
        try:
            cur = self.db.cursor()
            cur.execute("select * from lychee_albums where title=%s AND parent=%s", (album_name, parent))
            row = cur.fetchall()
            if len(row) != 0:
                res = True
        except Exception as e:
            logger.exception(e)
        finally:
            return res

    def albumExists(self, album):
        """
        Check if an album exists based on its name
        Parameters: an album properties list. At least the name should be specified
        Returns None or the albumid if it exists
        """
        self.loadAlbumList()
        logger.debug("exists ? " + str(album))

        if album['name'] in self.albumslist.keys():
            return self.albumslist[album['name']]
        else:
            return None

    def getAlbumNameFromIdsList(self, list_id):
        album_names = ''
        try:
            albumids = ','.join(list_id)
            query = ("select title from lychee_albums where id in(" + albumids + ")")
            cur = self.db.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            album_names = [column['title'] for column in rows]
        except Exception as e:
            album_names = ''
            logger.error('impossible to execute ' + query)
            logger.exception(e)
        finally:
            return album_names

    def photoExistsByName(self, photo_name):
        res = None
        try:
            cur = self.db.cursor()
            cur.execute("select id from lychee_photos where title=%s", (photo_name))
            row = cur.fetchall()
            if len(row) != 0:
                logger.debug("photoExistsByName %s", row)
                res = row[0]['id']
        except Exception as e:
            logger.exception(e)
        finally:
            return res

    def photoExists(self, photo):
        """
        Check if a photo already exists in its album based on its original name or checksum
        Parameter:
        - photo: a valid LycheePhoto object
        Returns a boolean
        """
        res = False
        try:
            cur = self.db.cursor()
            cur.execute(
                "select * from lychee_photos where album=%s AND (title=%s OR checksum=%s)",
                (photo.albumid,
                 photo.originalname,
                 photo.checksum))
            row = cur.fetchall()
            if len(row) != 0:
                res = True

            # Add Warning if photo exists in another album

            cur = self.db.cursor()
            cur.execute(
                "select album from lychee_photos where (title=%s OR checksum=%s)",
                (photo.originalname,
                 photo.checksum))
            rows = cur.fetchall()
            album_ids = [r['album'] for r in rows]
            if len(album_ids) > 0:
                logger.debug(
                    "a photo with this name: %s or checksum: %s already exists in at least another album: %s",
                    photo.originalname,
                    photo.checksum,
                    self.getAlbumNameFromIdsList(album_ids))

        except Exception as e:
            logger.exception(e)
            logger.error("photoExists:", photo.srcfullpath, "won't be added to lychee")
            res = True
        finally:
            return res

    def createAlbum(self, album):
        """
        Creates an album
        Parameter:
        - album: the album properties list, at least the name should be specified
        Returns the created albumid or None
        """
        album['id'] = None

        query = (
            "insert into lychee_albums (title, sysstamp, public, password, parent) values ('{}',{},'{}',NULL,'{}')"
                .format(
                album['name'],
                datetime.datetime.now().strftime('%s'),
                str(self.conf["publicAlbum"]),
                album['parent'])
        )

        try:

            cur = self.db.cursor()
            logger.debug("try to createAlbum: %s", query)
            cur.execute(
                "insert into lychee_albums (title, sysstamp, public, password, parent) values (%s,%s,%s,NULL,%s)",
                (
                    album['name'],
                    datetime.datetime.now().strftime('%s'),
                    str(self.conf["publicAlbum"]),
                    str(album['parent']))
            )
            self.db.commit()
            rowId = None
            rowId = cur.lastrowid
            self.albumslist[album['name']] = rowId
            album['id'] = rowId

        except Exception as e:
            logger.exception(e)
            logger.error("createAlbum: %s -> %s", album['name'], str(album))
            album['id'] = None
        finally:
            return album['id']

    def eraseAlbum(self, album_id):
        """
        Deletes all photos of an album but don't delete the album itself
        Parameters:
        - album: the album properties list to erase.  At least its id must be provided
        Return list of the erased photo url
        """
        res = []
        query = "delete from lychee_photos where album = " + str(album_id) + ''
        selquery = "select url from lychee_photos where album = " + str(album_id) + ''
        try:
            cur = self.db.cursor()
            cur.execute(selquery)
            rows = cur.fetchall()
            for row in rows:
                res.append(row['url'])
            cur.execute(query)
            self.db.commit()
            logger.debug("album photos erased: %s", album_id)
        except Exception as e:
            logger.exception(e)
            logger.error(album_id)
            logger.error(query)
            logger.error(selquery)
            logger.error("eraseAlbum")
        finally:
            return res

    def setAlbumParentAndTitle(self, title, parents, id):
        res = True
        album_query = "update lychee_albums set title = '" + str(title) + "', parent='" + str(
            parents) + "' where id = " + str(id)
        try:
            cur = self.db.cursor()
            cur.execute(album_query)
            self.db.commit()
        except Exception as e:
            logger.exception(e)
            res = False
        finally:
            return res

    def setPhotoAlbumAndTitle(self, title, Album, id):
        res = True
        album_query = "update lychee_photos set title = '" + str(title) + "', album='" + str(
            Album) + "' where id='" + str(id) + "'"
        try:
            cur = self.db.cursor()
            cur.execute(album_query)
            self.db.commit()
        except Exception as e:
            logger.exception(e)
            res = False
        finally:
            return res

    def dropAlbum(self, album_id):
        res = False
        query = "delete from lychee_albums where id = " + str(album_id) + ''
        try:
            cur = self.db.cursor()
            cur.execute(query)
            self.db.commit()
            logger.debug("album dropped: %s", album_id)
            res = True
        except Exception as e:
            logger.exception(e)
        finally:
            return res

    def dropPhoto(self, photo_id):
        """ delete a photo. parameter: photo_id """
        res = False
        query = "delete from lychee_photos where id = " + str(photo_id) + ''
        try:
            cur = self.db.cursor()
            cur.execute(query)
            self.db.commit()
            logger.debug("photo dropped: %s", photo_id)
            res = True
        except Exception as e:
            logger.exception(e)
        finally:
            return res

    def get_photo(self, photo):
        p = {}
        try:
            cur = self.db.cursor()
            cur.execute(
                "select * from lychee_photos where album=%s AND (title=%s OR checksum=%s)",
                (photo.albumid,
                 photo.originalname,
                 photo.checksum))
            row = cur.fetchone()
            if row is not None:
                p = {'url': row['url'], 'id': row['id'], 'album': row['album']}
            else:
                p = None
        except Exception as e:
            logger.exception(e)
        finally:
            return p

    def get_photo_light(self, album, name, checksum):
        p = {}
        try:
            cur = self.db.cursor()
            cur.execute(
                "select * from lychee_photos where album=%s AND (title=%s OR checksum=%s)",
                (album,
                 name,
                 checksum))
            row = cur.fetchone()
            if row is not None:
                p = {'url': row['url'], 'id': row['id'], 'album': row['album']}
            else:
                p = None

        except Exception as e:
            logger.exception(e)
        finally:
            return p

    def rename_photo(self, photo_id, new_name):
        res = True
        album_query = "update lychee_phots set title = '" + str(new_name) + "' where id = " + str(photo_id)
        try:
            cur = self.db.cursor()
            cur.execute(album_query)
            self.db.commit()
        except Exception as e:
            logger.exception(e)
            res = False
        finally:
            return res

    def get_all_photos(self, album_id=None):
        """
        Lists all photos in leeche db (used to delete all files)
        Return a photo url list
        """
        res = []
        if not (album_id):
            selquery = "select id, url, album  from lychee_photos"
        else:
            selquery = "select id, url, album  from lychee_photos where album={}".format(album_id)

        try:
            cur = self.db.cursor()
            cur.execute(selquery)
            rows = cur.fetchall()
            for row in rows:
                p = {'url': row['url'], 'id': row['id'], 'album': row['album']}
                res.append(p)
        except Exception as e:
            logger.exception(e)
        finally:
            return res

    def get_empty_albums(self):
        res = []
        try:
            # check if exists in db
            sql = "select id from lychee_albums where id not in(select distinct album from lychee_photos)"
            with self.db.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
            if rows:
                res = [r['id'] for r in rows]
        except Exception as e:
            logger.exception(e)
            res = None
            raise e
        finally:
            return res

    def get_album_id(self, album_name, parent_id):
        res = None
        try:
            # check if exists in db
            sql = "select id from lychee_albums WHERE title=%s AND parent=%s"
            with self.db.cursor() as cursor:
                cursor.execute(sql, (album_name, parent_id))
                rows = cursor.fetchone()
            res = rows
        except Exception as e:
            # logger.exception(e)
            res = None
            raise e
        finally:
            return res

    def get_album_ids_titles(self):
        res = None
        try:
            # check if exists in db
            sql = "select id, title from lychee_albums"
            with self.db.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
            res = rows
        except Exception as e:
            # logger.exception(e)
            res = None
            raise e
        finally:
            return res

    def get_album_parents(self, album_id=0):
        res = None
        try:
            # check if exists in db
            sql = "select parent from lychee_albums where id={}".format(album_id)
            with self.db.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchone()
                parents = rows['parent'].split(',')
                for parent in parents:
                    sql = "select id, title from lychee_albums where id={}".format(parent)
                    with self.db.cursor() as cursor2:
                        cursor2.execute(sql)
                        rows = cursor2.fetchall()
                    res = rows
        except Exception as e:
            # logger.exception(e)
            res = None
            raise e
        finally:
            return res

    def addFileToAlbum(self, photo):
        """
        Add a photo to an album
        Parameter:
        - photo: a valid LycheePhoto object
        Returns a boolean
        """
        res = True


        try:
            stamp = parse(photo.exif.takedate + ' ' + photo.exif.taketime).strftime('%s')
        except Exception as e:

            stamp = datetime.datetime.now().strftime('%s')

        query = ("insert into lychee_photos " +
                 "(id, url, public, type, width, height, " +
                 "size, star, " +
                 "thumbUrl, album,iso, aperture, make, " +
                 "model, shutter, focal, takestamp, " +
                 "description, title, checksum, tags) " +
                 "values " +
                 "({}, '{}', {}, '{}', {}, {}, " +
                 "'{}', {}, " +
                 "'{}', '{}', %s, %s," +
                 " %s, " +
                 "%s, %s, %s, '{}', " +
                 "%s, %s, '{}', %s)"
                 ).format(photo.id, photo.url, self.conf["publicAlbum"], photo.type, photo.width, photo.height,
                          photo.size, photo.star,
                          photo.thumbUrl, photo.albumid,
                          stamp,
                          photo.checksum)
        try:
            logger.debug(query)
            cur = self.db.cursor()
            res = cur.execute(query, (photo.exif.iso,
                                      photo.exif.aperture,
                                      photo.exif.make,
                                      photo.exif.model, photo.exif.shutter, photo.exif.focal,
                                      photo.description, photo.originalname, photo.tags))
            self.db.commit()
        except Exception as e:
            logger.exception(e)
            logger.error("addFileToAlbum : %s", photo)
            logger.error("addFileToAlbum while executing: %s", cur._last_executed)
            res = False
        finally:
            return res

    def reinitAlbumAutoIncrement(self):

        min, max = self.getAlbumMinMaxIds()
        if max:
            qry = "alter table lychee_albums AUTO_INCREMENT=" + str(max + 1)
            try:
                cur = self.db.cursor()
                cur.execute(qry)
                self.db.commit()
                logger.debug("reinit auto increment to %s", str(max + 1))
            except Exception as e:
                logger.exception(e)

    def close(self):
        """
        Close DB Connection
        Returns nothing
        """
        if self.db:
            self.db.close()

    def dropAll(self):
        """
        Drop all albums and photos from DB
        Returns nothing
        """
        try:
            cur = self.db.cursor()
            cur.execute("TRUNCATE TABLE lychee_albums")
            cur.execute("TRUNCATE TABLE lychee_photos")
            self.db.commit()
        except Exception as e:
            logger.exception(e)
