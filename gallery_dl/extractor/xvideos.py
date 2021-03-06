# -*- coding: utf-8 -*-

# Copyright 2017-2018 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Extract images from https://www.xvideos.com/"""

from .common import Extractor, Message
from .. import text, util, exception
import json


class XvideosExtractor(Extractor):
    """Base class for xvideos extractors"""
    category = "xvideos"

    def get_page(self):
        response = self.request(self.url, fatal=False)
        if response.status_code in (403, 404):
            raise exception.NotFoundError(self.subcategory)
        return response.text


class XvideosGalleryExtractor(XvideosExtractor):
    """Extractor for user profile galleries from xvideos.com"""
    subcategory = "gallery"
    directory_fmt = ["{category}", "{user[name]}", "{title}"]
    filename_fmt = "{category}_{gallery_id}_{num:>03}.{extension}"
    archive_fmt = "{gallery_id}_{num}"
    pattern = [r"(?:https?://)?(?:www\.)?xvideos\.com"
               r"/profiles/([^/?&#]+)/photos/(\d+)"]
    test = [
        (("https://www.xvideos.com/profiles"
          "/pervertedcouple/photos/751031/random_stuff"), {
            "url": "4f0d992e5dc39def2c3ac8e099d17bf09e76e3c7",
            "keyword": "71d64a9b2ba7015850d3aed3fbcae1e7e0481515",
        }),
        ("https://www.xvideos.com/profiles/pervertedcouple/photos/751032/", {
            "exception": exception.NotFoundError,
        }),
    ]

    def __init__(self, match):
        XvideosExtractor.__init__(self)
        self.user, self.gid = match.groups()
        self.url = "https://www.xvideos.com/profiles/{}/photos/{}".format(
            self.user, self.gid)

    def items(self):
        page = self.get_page()
        data = self.get_metadata(page)
        imgs = self.get_images(page)
        data["count"] = len(imgs)
        yield Message.Version, 1
        yield Message.Directory, data
        for url in imgs:
            data["num"] = util.safe_int(url.rsplit("_", 2)[1])
            data["extension"] = url.rpartition(".")[2]
            yield Message.Url, url, data

    def get_metadata(self, page):
        """Collect metadata for extractor-job"""
        data = text.extract_all(page, (
            ("userid" , '"id_user":', ','),
            ("display", '"display":"', '"'),
            ("title"  , '"title":"', '"'),
            ("descr"  , '<small>', '</small>'),
            ("tags"   , '<em>Tagged:</em>', '<'),
        ))[0]

        return {
            "user": {
                "id": util.safe_int(data["userid"]),
                "name": self.user,
                "display": data["display"],
                "description": text.remove_html(data["descr"]).strip(),
            },
            "tags": text.unescape(data["tags"] or "").strip().split(", "),
            "title": text.unescape(data["title"]),
            "gallery_id": util.safe_int(self.gid),
        }

    @staticmethod
    def get_images(page):
        """Return a list of all image urls for this gallery"""
        return list(text.extract_iter(
            page, '<a class="embed-responsive-item" href="', '"'))


class XvideosUserExtractor(XvideosExtractor):
    """Extractor for user profiles from xvideos.com"""
    subcategory = "user"
    categorytransfer = True
    pattern = [r"(?:https?://)?(?:www\.)?xvideos\.com"
               r"/profiles/([^/?&#]+)/?(?:#.*)?$"]
    test = [
        ("https://www.xvideos.com/profiles/pervertedcouple", {
            "url": "a413f3e60d6d3a2de79bd44fa3b7a9c03db4336e",
            "keyword": "a796760d34732adc7ec52a8feb057515209a2ca6",
        }),
        ("https://www.xvideos.com/profiles/niwehrwhernvh", {
            "exception": exception.NotFoundError,
        }),
        ("https://www.xvideos.com/profiles/pervertedcouple#_tabPhotos", None),
    ]

    def __init__(self, match):
        XvideosExtractor.__init__(self)
        self.user = match.group(1)
        self.url = "https://www.xvideos.com/profiles/" + self.user

    def items(self):
        page = self.get_page()
        data = json.loads(text.extract(
            page, "xv.conf=", ";</script>")[0])["data"]

        if not isinstance(data["galleries"], dict):
            return
        if "0" in data["galleries"]:
            del data["galleries"]["0"]

        galleries = [
            {"gallery_id": util.safe_int(gid),
             "title": text.unescape(gdata["title"]),
             "count": gdata["nb_pics"]}
            for gid, gdata in data["galleries"].items()
        ]
        galleries.sort(key=lambda x: x["gallery_id"])

        yield Message.Version, 1
        for gallery in galleries:
            url = "https://www.xvideos.com/profiles/{}/photos/{}".format(
                self.user, gallery["gallery_id"])
            yield Message.Queue, url, gallery
