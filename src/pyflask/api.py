from __future__ import print_function
import config
import json
import logging
import logging.handlers
import os

from flask import Flask
from flask_cors import CORS
from flask_restx import Api, Resource, reqparse

from zenodo import (
    getAllZenodoDepositions,
    createNewZenodoDeposition,
    uploadFileToZenodoDeposition,
    addMetadataToZenodoDeposition,
    publishZenodoDeposition,
    deleteZenodoDeposition,
)
from metadata import createMetadata, createCitationCFF
from utilities import (
    foldersPresent,
    zipFolder,
    deleteFile,
    requestJSON,
    createFile,
    openFileExplorer,
)

API_VERSION = "0.0.1"


app = Flask(__name__)
app.config.SWAGGER_UI_DOC_EXPANSION = "list"  # full if you want to see all the details
CORS(app)

# configure root logger
LOG_FOLDER = os.path.join(os.path.expanduser("~"), ".sodaforcovid19research", "logs")
LOG_FILENAME = "api.log"
LOG_PATH = os.path.join(LOG_FOLDER, LOG_FILENAME)

if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)

# Add the log message handler to the logger
handler = logging.handlers.RotatingFileHandler(
    LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3
)

# create logging formatter
logFormatter = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(logFormatter)

app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)

api = Api(
    app,
    version=API_VERSION,
    title="SODA for COVID-19 Research backend api",
    description="The backend api system for the Electron Vue app",
    doc="/docs",
)


@api.route("/api_version", endpoint="apiVersion")
class ApiVersion(Resource):
    def get(self):
        """Returns the semver version number of the current API"""
        api.logger.warning("TEST")
        return API_VERSION


@api.route("/echo", endpoint="echo")
class HelloWorld(Resource):
    @api.response(200, "Success")
    @api.response(400, "Validation Error")
    def get(self):
        """Returns a simple 'Server Active' message"""

        response = "Server active!"

        return response


###############################################################################
# Metadata operations
###############################################################################

metadata = api.namespace("metadata", description="Metadata operations")


@metadata.route("/create", endpoint="CreateMetadata")
class CreateMetadata(Resource):
    @metadata.doc(
        responses={200: "Success"},
        params={
            "data_types": "Types of data.",
            "data_object": "Full data object to create metadata from. Should have keys from the `data_types` parameter",  # noqa: E501
            "virtual_file": "Parameter to generate a virtual file",
        },
    )
    def post(self):
        """Create the codemetadata json file"""
        parser = reqparse.RequestParser()

        parser.add_argument("data_types", type=str, help="Types of data ")
        parser.add_argument(
            "data_object", type=str, help="Complete data object to create metadata"
        )
        parser.add_argument(
            "virtual_file", type=bool, help="Parameter to generate a virtual file"
        )

        args = parser.parse_args()

        data_types = json.loads(args["data_types"])
        data = json.loads(args["data_object"])
        virtual_file = args["virtual_file"]

        return createMetadata(data_types, data, virtual_file)


@metadata.route("/citation/create", endpoint="CreateCitationCFF")
class CreateCitationCFF(Resource):
    @metadata.doc(
        responses={200: "Success"},
        params={
            "data_types": "Types of data.",
            "data_object": "Full data object to create metadata from. Should have keys from the `data_types` parameter",  # noqa: E501
            "virtual_file": "Parameter to generate a virtual file",
        },
    )
    def post(self):
        """Create the citation cff file"""
        parser = reqparse.RequestParser()

        parser.add_argument("data_types", type=str, help="Types of data ")
        parser.add_argument(
            "data_object", type=str, help="Complete data object to create metadata"
        )
        parser.add_argument(
            "virtual_file", type=bool, help="Parameter to generate a virtual file"
        )

        args = parser.parse_args()

        data_types = json.loads(args["data_types"])
        data = json.loads(args["data_object"])
        virtual_file = args["virtual_file"]

        return createCitationCFF(data_types, data, virtual_file)


###############################################################################
# Zenodo API operations
###############################################################################

zenodo = api.namespace("zenodo", description="Zenodo operations")


@zenodo.route("/env", endpoint="zenodoURL")
class zenodoURL(Resource):
    def get(self):
        """Returns the zenodo endpoint url. If the response is sandbox.zenodo.org, this corresponds to the testing environment. zenodo.org only will correspond to the production environment."""  # noqa: E501
        return config.ZENODO_SERVER_URL


@zenodo.route("/depositions", endpoint="zenodoGetAll")
class zenodoGetAll(Resource):
    @zenodo.doc(
        responses={200: "Success", 401: "Authentication error"},
        params={"access_token": "Zenodo access token required with every request."},
    )
    def get(self):
        """Get a list of all the Zenodo depositions"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "access_token",
            type=str,
            required=True,
            help="access_token is required. accessToken needs to be of type str",
        )

        args = parser.parse_args()

        access_token = args["access_token"]

        response = getAllZenodoDepositions(access_token)
        return response


@zenodo.route("/new", endpoint="zenodoCreateNew")
class zenodoCreateNew(Resource):
    @zenodo.doc(
        responses={200: "Success", 401: "Authentication error", 400: "Bad request"},
        params={"access_token": "Zenodo access token required with every request."},
    )
    def post(self):
        """Create a new empty Zenodo deposition"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "access_token",
            type=str,
            required=True,
            help="access_token is required. accessToken needs to be of type str",
        )

        args = parser.parse_args()

        access_token = args["access_token"]

        response = createNewZenodoDeposition(access_token)
        return response


@zenodo.route("/upload", endpoint="zenodoUploadFile")
class zenodoUploadFile(Resource):
    @zenodo.doc(
        responses={200: "Success", 401: "Authentication error"},
        params={
            "access_token": "Zenodo access token required with every request.",
            "bucket_url": "bucket url is found in zenodo.links.bucket",
            "file_path": "file path of file to upload",
        },
    )
    def post(self):
        """Upload a file into a zenodo deposition"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "access_token",
            type=str,
            required=True,
            help="access_token is required. accessToken needs to be of type str",
        )
        parser.add_argument(
            "bucket_url",
            type=str,
            required=True,
            help="bucket_url is required. bucket_url needs to be of type str",
        )
        parser.add_argument(
            "file_path",
            type=str,
            required=True,
            help="file_path is required. accessToken needs to be of type str",
        )

        args = parser.parse_args()

        access_token = args["access_token"]
        bucket_url = args["bucket_url"]
        file_path = args["file_path"]

        return uploadFileToZenodoDeposition(access_token, bucket_url, file_path)


@zenodo.route("/metadata", endpoint="zenodoAddMetadata")
class zenodoAddMetadata(Resource):
    @zenodo.doc(
        responses={200: "Success", 401: "Authentication error"},
        params={
            "access_token": "Zenodo access token required with every request.",
            "deposition_id": "deposition id is found in zenodo.id",
            "metadata": "json string with metadata to add to the deposition",
        },
    )
    def post(self):
        """Add metadata to a zenodo deposition"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "access_token",
            type=str,
            required=True,
            help="access_token is required. accessToken needs to be of type str",
        )
        parser.add_argument(
            "deposition_id",
            type=str,
            required=True,
            help="deposition_id is required. deposition_id needs to be of type str",
        )
        parser.add_argument(
            "metadata",
            type=str,
            required=True,
            help="metadata is required. metadata needs to be a json string",
        )

        args = parser.parse_args()

        access_token = args["access_token"]
        deposition_id = args["deposition_id"]
        metadata = json.loads(args["metadata"])

        return addMetadataToZenodoDeposition(access_token, deposition_id, metadata)


@zenodo.route("/publish", endpoint="zenodoPublish")
class zenodoPublish(Resource):
    @zenodo.doc(
        responses={200: "Success", 401: "Authentication error"},
        params={
            "access_token": "Zenodo access token required with every request.",
            "deposition_id": "deposition id of the zenodo object",
        },
    )
    def post(self):
        """Publish a zenodo deposition"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "access_token",
            type=str,
            required=True,
            help="access_token is required. accessToken needs to be of type str",
        )
        parser.add_argument(
            "deposition_id",
            type=str,
            required=True,
            help="deposition_id is required. deposition_id needs to be of type str",
        )

        args = parser.parse_args()

        access_token = args["access_token"]
        deposition_id = args["deposition_id"]

        return publishZenodoDeposition(access_token, deposition_id)


@zenodo.route("/delete", endpoint="zenodoDelete")
class zenodoDelete(Resource):
    @zenodo.doc(
        responses={200: "Success", 401: "Authentication error"},
        params={
            "access_token": "Zenodo access token required with every request.",
            "deposition_id": "deposition id of the zenodo object",
        },
    )
    def delete(self):
        """Delete a zenodo deposition"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "access_token",
            type=str,
            required=True,
            help="access_token is required. accessToken needs to be of type str",
        )
        parser.add_argument(
            "deposition_id",
            type=str,
            required=True,
            help="deposition_id is required. deposition_id needs to be of type str",
        )

        args = parser.parse_args()

        access_token = args["access_token"]
        deposition_id = args["deposition_id"]

        return deleteZenodoDeposition(access_token, deposition_id)


###############################################################################
# Utilities
###############################################################################


utilities = api.namespace("utilities", description="utilities for random tasks")


@utilities.route("/checkforfolders", endpoint="checkForFolders")
class checkForFolders(Resource):
    @utilities.doc(
        responses={200: "Success", 400: "Validation error"},
        params={
            "folder_path": "folder path to check if sub folders are present.",
        },
    )
    def post(self):
        """Checks if folders are present in the currently provided path"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "folder_path",
            type=str,
            required=True,
            help="folder path to check if sub folders are present.",
        )

        args = parser.parse_args()

        folder_path = args["folder_path"]

        return foldersPresent(folder_path)


@utilities.route("/zipfolder", endpoint="ZipFolder")
class ZipFolder(Resource):
    @utilities.doc(
        responses={200: "Success", 400: "Validation error"},
        params={
            "folder_path": "folder path to zip.",
        },
    )
    def post(self):
        """Zips a folder"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "folder_path",
            type=str,
            required=True,
            help="folder path to zip.",
        )

        args = parser.parse_args()

        folder_path = args["folder_path"]

        return zipFolder(folder_path)


@utilities.route("/deletefile", endpoint="deleteFile")
class DeleteFile(Resource):
    @utilities.doc(
        responses={200: "Success", 400: "Validation error"},
        params={
            "file_path": "file path to delete.",
        },
    )
    def post(self):
        """Deletes a file"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "file_path",
            type=str,
            required=True,
            help="file path to delete.",
        )

        args = parser.parse_args()

        file_path = args["file_path"]
        return deleteFile(file_path)


@utilities.route("/requestjson", endpoint="RequestJSON")
class RequestJSON(Resource):
    @utilities.doc(
        responses={200: "Success", 400: "Validation error"},
        params={
            "url": "url to request from the web.",
        },
    )
    def post(self):
        """request a json file from the web"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "url",
            type=str,
            required=True,
            help="url that needs a CORS proxy",
        )

        args = parser.parse_args()

        url = args["url"]
        return requestJSON(url)


@utilities.route("/createfile", endpoint="CreateFile")
class CreateFile(Resource):
    @utilities.doc(
        responses={200: "Success", 400: "Validation error"},
        params={
            "folder_path": "folder path to generate files in",
            "file_name": "name of the file to generate",
            "file_content": "content of the file. Will be string",
            "content_type": "content type to determine what it is written with",
        },
    )
    def post(self):
        """create a file in the provided folder path"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "folder_path",
            type=str,
            required=True,
            help="folder path to generate files in",
        )
        parser.add_argument(
            "file_name",
            type=str,
            required=True,
            help="name of the file to generate",
        )
        parser.add_argument(
            "file_content",
            type=str,
            required=True,
            help="content of the file",
        )
        parser.add_argument(
            "content_type",
            type=str,
            required=True,
            help="content type to determine what it is written with",
        )

        args = parser.parse_args()

        folder_path = args["folder_path"]
        file_name = args["file_name"]
        file_content = args["file_content"]
        content_type = args["content_type"]

        return createFile(folder_path, file_name, file_content, content_type)


@utilities.route("/openFileExplorer", endpoint="OpenFileExplorer")
class RequestJSON(Resource):
    @utilities.doc(
        responses={200: "Success", 400: "Validation error"},
        params={
            "folder_path": "open file at path",
        },
    )
    def post(self):
        """create a file in the provided folder path"""
        parser = reqparse.RequestParser()

        parser.add_argument(
            "folder_path",
            type=str,
            required=True,
            help="file path to open file explorer at",
        )
        args = parser.parse_args()
        folder_path = args["folder_path"]

        return openFileExplorer(folder_path)


# 5000 is the flask default port.
# Using 7632 since it spells SODA lol.
# Remove `debug=True` when creating the standalone pyinstaller file
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7632)
    # app.run(host="127.0.0.1", port=7632, debug=True)
