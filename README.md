# Thumbnail service

This is a flask application that generates thumbnails from data stored on the
[LCOGT Science Archive](https://developers.lcogt.net/pages/archive.html).

## Authorization

The api passes through the `Authorization` header to the archive API. You only need to provide
this header if the data you are attempting to get a thumbnail for is proprietary. See the archive
documentation for more details.

## Endpoints

There are only 2 endpoints: `/<frame_id>/` and `/<basename>/` where `frame_id` is the ID of the frame
in the archive, and `basename` is the base part of the filename (no file extension) you wish to make
a thumbnail of. Using the frame_id is faster to return if you happen to know it
ahead of time.

Both endpoints take 3 query parameters:

* width
* height
* label

Width and height are in pixels, label will appear as white text in the lower left had corner of the image.

They both **return a url** to the thumbnail file that will be good for 1 week.


## Example

[https://thumbnails.lcogt.net/3863274/?width=500&height=500&label=So many stars!](https://thumbnails.lcogt.net/3863274/?width=500&height=500&label=So many stars!)
