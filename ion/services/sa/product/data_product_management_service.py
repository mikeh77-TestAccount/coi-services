#!/usr/bin/env python

__author__ = 'Maurice Manning'
__license__ = 'Apache 2.0'

from pyon.util.log import log
from interface.services.sa.idata_product_management_service import BaseDataProductManagementService
from ion.services.sa.product.data_product_impl import DataProductImpl
from interface.objects import IngestionQueue, DataProductVersion

from pyon.core.exception import BadRequest, NotFound
from pyon.public import RT, PRED, LCS



class DataProductManagementService(BaseDataProductManagementService):
    """ @author     Bill Bollenbacher
        @file       ion/services/sa/product/data_product_management_service.py
        @brief      Implementation of the data product management service
    """
    
    def on_init(self):
        self.override_clients(self.clients)

    def override_clients(self, new_clients):
        """
        Replaces the service clients with a new set of them... and makes sure they go to the right places
        """
        self.data_product   = DataProductImpl(self.clients)

    

    def create_data_product(self, data_product=None, stream_definition_id=''):
        """
        @param      data_product IonObject which defines the general data product resource
        @param      source_resource_id IonObject id which defines the source for the data
        @retval     data_product_id
        """
        
        # Create will validate and register a new data product within the system

        # Register - create and store a new DataProduct resource using provided metadata
        log.debug("DataProductManagementService:create_data_product: %s" % str(data_product))
        data_product_id = self.data_product.create_one(data_product)

        #create the initial/default data product version
        data_product_version = DataProductVersion()
        data_product_version.name = "default"
        data_product_version.description = "initial version"
        dpv_id, rev = self.clients.resource_registry.create(data_product_version)
        self.clients.resource_registry.create_association( subject=data_product_id, predicate=PRED.hasVersion, object=dpv_id)

        #Create the stream if a stream definition is provided
        log.debug("DataProductManagementService:create_data_product: stream definition id = %s" % stream_definition_id)

        if stream_definition_id:
            stream_id = self.clients.pubsub_management.create_stream(name=data_product.name,  description=data_product.description, stream_definition_id=stream_definition_id)
            # Associate the Stream with the main Data Product and with the default version
            self.data_product.link_stream(data_product_id, stream_id)
            self.clients.resource_registry.create_association( subject=dpv_id, predicate=PRED.hasStream, object=stream_id)

        # Return the id of the new data product
        return data_product_id


    def read_data_product(self, data_product_id=''):
        """
        method docstring
        """
        # Retrieve all metadata for a specific data product
        # Return data product resource

        log.debug("DataProductManagementService:read_data_product: %s" % str(data_product_id))
        
        result = self.data_product.read_one(data_product_id)
        
        return result


    def update_data_product(self, data_product=None):
        """
        @todo document this interface!!!

        @param data_product    DataProduct
        @throws NotFound    object with specified id does not exist
        """
 
        log.debug("DataProductManagementService:update_data_product: %s" % str(data_product))
               
        self.data_product.update_one(data_product)

        #TODO: any changes to producer? Call DataAcquisitionMgmtSvc?

        return


    def delete_data_product(self, data_product_id=''):

        #Check if this data product is associated to a producer
        #todo: convert to impl call
        producer_ids = self.data_product.find_stemming_data_producer(data_product_id)

        for producer_id in producer_ids:
            log.debug("DataProductManagementService:delete_data_product unassigning data producers: %s")
            self.clients.data_acquisition_management.unassign_data_product(producer_id, data_product_id)

        #todo: remove stream?

#        # find any stream links
#        stream_ids, _ = self.clients.resource_registry.find_objects(data_product_id, PRED.hasStream, RT.Stream, id_only=True)
#
#        # delete the stream associations link first
#        stream_assocs = self.clients.resource_registry.find_associations(data_product_id, PRED.hasStream)
#        for stream_assoc in stream_assocs:
#            self.clients.resource_registry.delete_association(stream_assoc)
#
#        for stream_id in stream_ids:
#            self.clients.pubsub_management.delete_stream(stream_id)
#
#        # delete the hasOutputDataProduct associations link
#        dp_assocs = self.clients.resource_registry.find_associations(data_product_id, PRED.hasOutputProduct)
#        for dp_assoc in dp_assocs:
#            self.clients.resource_registry.delete_association(dp_assoc)
#        # delete the hasInputDataProduct associations link
#        dp_assocs = self.clients.resource_registry.find_associations(data_product_id, PRED.hasInputProduct)
#        for dp_assoc in dp_assocs:
#            self.clients.resource_registry.delete_association(dp_assoc)

        # Delete the data product
        data_product_obj = self.read_data_product(data_product_id)

        if data_product_obj.lcstate != LCS.RETIRED:
            self.data_product.delete_one(data_product_id)
        #self.clients.resource_registry.delete(data_product_id)
        #self.clients.resource_registry.set_lifecycle_state(data_product_id, LCS.RETIRED)
        return

    def hard_delete_data_product(self, data_product_id=''):

        return


    def find_data_products(self, filters=None):
        """
        method docstring
        """
        # Validate the input filter and augment context as required

        # Define set of resource attributes to filter on, change parameter from "filter" to include attributes and filter values.
        #     potentially: title, keywords, date_created, creator_name, project, geospatial coords, time range

        # Call DM DiscoveryService to query the catalog for matches

        # Organize and return the list of matches with summary metadata (title, summary, keywords)

        return self.data_product.find_some(filters)



    def activate_data_product_persistence(self, data_product_id='', persist_data=True, persist_metadata=True):
        """Persist data product data into a data set

        @param data_product_id    str
        @throws NotFound    object with specified id does not exist
        """
        # retrieve the data_process object
        data_product_obj = self.data_product.read_one(data_product_id)

        # get the Stream associated with this data product; if no stream then create one, if multiple streams then Throw
        streams = self.data_product.find_stemming_stream(data_product_id)
        if not streams:
            raise BadRequest('Data Product %s must have one stream associated' % str(data_product_id))

        #todo: what if there are multiple streams?
        stream_id = streams[0]._id
        log.debug("activate_data_product_persistence: stream = %s"  % str(stream_id))


        #--------------------------------------------------------------------------------
        # Create the ingestion config for this exchange
        #--------------------------------------------------------------------------------
#        self.exchange_point       = 'science_data'
#        self.exchange_space       = 'science_granule_ingestion'
#        ingest_queue = IngestionQueue(name=self.exchange_space, type='science_granule')
#        ingestion_configuration_id = self.clients.ingestion_management.create_ingestion_configuration(name='standard_ingest', exchange_point_id=self.exchange_point, queues=[ingest_queue])
#
#        log.debug("activate_data_product_persistence: ingestion_configuration_id = %s"  % str(ingestion_configuration_id))

        #--------------------------------------------------------------------------------
        # Persist the data stream
        #--------------------------------------------------------------------------------

        ingestion_configuration_id = self.clients.ingestion_management.list_ingestion_configurations(id_only=True)[0]

        dataset_id = self.clients.ingestion_management.persist_data_stream(stream_id=stream_id, ingestion_configuration_id=ingestion_configuration_id)
        log.debug("activate_data_product_persistence: dataset_id = %s"  % str(dataset_id))
        self.data_product.link_data_set(data_product_id, dataset_id)

        # todo: dataset_configuration_obj contains the ingest config for now...
        data_product_obj.dataset_configuration_id = ingestion_configuration_id
        self.update_data_product(data_product_obj)

    def suspend_data_product_persistence(self, data_product_id=''):
        """Suspend data product data persistnce into a data set, multiple options

        @param data_product_id    str
        @param type    str
        @throws NotFound    object with specified id does not exist
        """

        log.debug("suspend_data_product_persistence: data_product_id = %s"  % str(data_product_id))

        # retrieve the data_process object
        data_product_obj = self.clients.resource_registry.read(data_product_id)
        if data_product_obj is None:
            raise NotFound("Data Product %s does not exist" % data_product_id)
        if data_product_obj.dataset_configuration_id is None:
            raise NotFound("Data Product %s dataset configuration does not exist" % data_product_id)

        # get the Stream associated with this data product; if no stream then create one, if multiple streams then Throw
        #streams = self.data_product.find_stemming_stream(data_product_id)
        stream_ids, _ = self.clients.resource_registry.find_objects(subject=data_product_id, predicate=PRED.hasStream, object_type=RT.Stream, id_only=True)
        if not stream_ids:
            raise BadRequest('Data Product %s must have one stream associated' % str(data_product_id))

        #todo: what if there are multiple streams?
        stream_id = stream_ids[0]
        log.debug("suspend_data_product_persistence: stream = %s"  % str(stream_id))


        # todo: dataset_configuration_obj contains the ingest config for now...
        ret = self.clients.ingestion_management.unpersist_data_stream(stream_id=stream_id, ingestion_configuration_id=data_product_obj.dataset_configuration_id)

        log.debug("suspend_data_product_persistence: deactivate = %s"  % str(ret))

        #detach the dataset from this data product
#        dataset_ids,other = self.clients.resource_registry.find_objects(subject=data_product_id, predicate=PRED.hasDataset, id_only=True)
#        for dataset_id in dataset_ids:
#         self.data_product.unlink_data_set(data_product_id, dataset_id)
        

    def create_data_product_version(self, data_product_id='', data_product_version=None):
        """Define a new version of an existing set of information that represent an inprovement in the quality or
        understanding of the information. Only creates the second and higher versions of a DataProduct.
        The first version is implicit in the crate_data_product() operation.

        @param data_product_id    str
        @param data_product_version    DataProductVersion
        @retval data_product_version_id    str
        @throws BadRequest    if object does not have _id or _rev attribute
        @throws NotFound    object with specified id does not exist
        """
        data_product_obj = self.read_data_product(data_product_id)

        data_product_version_id, version = self.clients.resource_registry.create(data_product_version)
        self.clients.resource_registry.create_association( subject=data_product_id, predicate=PRED.hasVersion, object=data_product_version_id)

        stream_ids, _ = self.clients.resource_registry.find_objects(subject=data_product_id, predicate=PRED.hasStream, id_only=True)
        if stream_ids:
            #use the first steam, but this should be validated
            streamdef_ids, _ = self.clients.resource_registry.find_objects(subject=stream_ids[0], predicate=PRED.hasStreamDefinition, id_only=True)
            stream_id = self.clients.pubsub_management.create_stream(name=data_product_obj.name,  description=data_product_obj.description, stream_definition_id=streamdef_ids[0])
            log.debug("create_data_product_version: create stream stream_id %s" % stream_id)
            # Associate the Stream with  this version
            self.clients.resource_registry.create_association( subject=data_product_version_id, predicate=PRED.hasStream, object=stream_id)
        else:
            raise NotFound("Data Product %s does not have a connected StreamDefinition" % data_product_id)

        return data_product_version_id

    def update_data_product_version(self, data_product=None):
        """@todo document this interface!!!

        @param data_product    DataProductVersion
        @throws NotFound    object with specified id does not exist
        """
        log.debug("DataProductManagementService:update_data_product_version: %s" % str(data_product))

        self.clients.resource_registry.update(data_product)

        #TODO: any changes to producer? Call DataAcquisitionMgmtSvc?

        return

    def read_data_product_version(self, data_product_version_id=''):
        """Retrieve data product information

        @param data_product_version_id    str
        @retval data_product    DataProductVersion
        """
        log.debug("DataProductManagementService:read_data_product_version: %s" % str(data_product_version_id))

        result = self.clients.resource_registry.read(data_product_version_id)

        return result

    def delete_data_product_version(self, data_product_version_id=''):
        """Remove a version of an data product.

        @param data_product_version_id    str
        @throws BadRequest    if object does not have _id or _rev attribute
        @throws NotFound    object with specified id does not exist
        """
        pass


    def execute_data_product_lifecycle(self, data_product_id="", lifecycle_event=""):
       """
       declare a data_product to be in a given state
       @param data_product_id the resource id
       """
       return self.data_product.advance_lcs(data_product_id, lifecycle_event)

    def get_last_update(self, data_product_id=''):
        """@todo document this interface!!!

        @param data_product_id    str
        @retval last_update    LastUpdate
        @throws NotFound    Data product not found or cache for data product not found.
        """
        from ion.processes.data.last_update_cache import CACHE_DATASTORE_NAME
        datastore_name = CACHE_DATASTORE_NAME
        db = self.container.datastore_manager.get_datastore(datastore_name)
        stream_ids,other = self.clients.resource_registry.find_objects(subject=data_product_id, predicate=PRED.hasStream, id_only=True)
        retval = {}
        for stream_id in stream_ids:
            try:
                lu = db.read(stream_id)
                retval[stream_id] = lu
            except NotFound:
                continue
        return retval
