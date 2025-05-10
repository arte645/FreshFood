from concurrent import futures
import grpc
from database_pb2 import GetRequest, GetResponse, PostRequest, PostResponse, UpdateRequest, UpdateResponse, DeleteRequest, DeleteResponse
from database_pb2_grpc import DatabaseServiceServicer, add_DatabaseServiceServicer_to_server
from fastapi import FastAPI, Depends, HTTPException, Response, Request
import asyncio
from dotenv import load_dotenv
import os
from database_pb2_grpc import DatabaseServiceStub
from supabase import create_client, Client
import json

load_dotenv()

class DatabaseService(DatabaseServiceServicer):
    def __init__(self):
        self.supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    
    def Get(self, request: GetRequest, context):
        rule_of_selection = request.rule_of_selection.split("/")
        column, eqv = rule_of_selection[0], rule_of_selection[1]
        response = (
            self.supabase.table(request.table)
            .select(request.selected_columns)
            .eq(column, eqv)
            .execute()
        )
        data_json = json.dumps(response.data)
        return GetResponse(data_json = data_json,
            status_code = 200)
    
    def Post(self, request, context):
        resp = (
                self.supabase.table(request.table)
                .insert(json.loads(request.inserted_columns_and_data))
                .execute()
            )
        return PostResponse(status_code = 200)
    
    def Update(self, request, context):
        resp = (
                self.supabase.table(request.table)
                .update(json.loads(request.inserted_columns_and_data))
                .eq(request.name_of_item_id, int(request.item_id))
                .execute()
            )
        return UpdateResponse(status_code = 200)
    
    def Delete(self, request, context):
        resp = (
                self.supabase.table(request.table)
                .delete()
                .eq(request.name_of_item_id, int(request.item_id))
                .execute()
            )
        return DeleteResponse(status_code = 200)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_DatabaseServiceServicer_to_server(DatabaseService(), server)
    server.add_insecure_port(f"[::]:{os.getenv('databaseHost')}")
    server.start()
    server.wait_for_termination()


serve()
