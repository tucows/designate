# Copyright 2012 Managed I.T.
#
# Author: Kiall Mac Innes <kiall@managedit.ie>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import time
from sqlalchemy.orm import exc
from moniker.openstack.common import cfg
from moniker.openstack.common import log as logging
from moniker import exceptions
from moniker.storage import base
from moniker.storage.impl_sqlalchemy import models
from moniker.sqlalchemy.session import get_session, get_engine, SQLOPTS

LOG = logging.getLogger(__name__)

cfg.CONF.register_group(cfg.OptGroup(
    name='storage:sqlalchemy', title="Configuration for SQLAlchemy Storage"
))

cfg.CONF.register_opts(SQLOPTS, group='storage:sqlalchemy')


class SQLAlchemyStorage(base.StorageEngine):
    __plugin_name__ = 'sqlalchemy'

    def get_connection(self):
        return Connection(self.name)


class Connection(base.Connection):
    """
    SQLAlchemy connection
    """
    def __init__(self, config_group):
        self.engine = get_engine(config_group)
        self.session = get_session(config_group)

    def setup_schema(self):
        """ Semi-Private Method to create the database schema """
        models.Base.metadata.create_all(self.session.bind)

    def teardown_schema(self):
        """ Semi-Private Method to reset the database schema """
        models.Base.metadata.drop_all(self.session.bind)

    # Server Methods
    def create_server(self, context, values):
        server = models.Server()

        server.update(values)

        try:
            server.save(self.session)
        except exceptions.Duplicate:
            raise exceptions.DuplicateServer()

        return dict(server)

    def get_servers(self, context, criterion=None):
        query = self.session.query(models.Server)

        if criterion:
            query = query.filter_by(**criterion)

        try:
            result = query.all()
        except exc.NoResultFound:
            LOG.debug('No results found')
            return []
        else:
            return [dict(o) for o in result]

    def _get_server(self, context, server_id):
        query = self.session.query(models.Server)

        server = query.get(server_id)

        if not server:
            raise exceptions.ServerNotFound(server_id)
        else:
            return server

    def get_server(self, context, server_id):
        server = self._get_server(context, server_id)

        return dict(server)

    def update_server(self, context, server_id, values):
        server = self._get_server(context, server_id)

        server.update(values)

        try:
            server.save(self.session)
        except exceptions.Duplicate:
            raise exceptions.DuplicateServer()

        return dict(server)

    def delete_server(self, context, server_id):
        server = self._get_server(context, server_id)

        server.delete(self.session)

    # TSIG Key Methods
    def create_tsigkey(self, context, values):
        tsigkey = models.TsigKey()

        tsigkey.update(values)

        try:
            tsigkey.save(self.session)
        except exceptions.Duplicate:
            raise exceptions.DuplicateTsigKey()

        return dict(tsigkey)

    def get_tsigkeys(self, context, criterion=None):
        query = self.session.query(models.TsigKey)

        if criterion:
            query = query.filter_by(**criterion)

        try:
            result = query.all()
        except exc.NoResultFound:
            LOG.debug('No results found')
            return []
        else:
            return [dict(o) for o in result]

    def _get_tsigkey(self, context, tsigkey_id):
        query = self.session.query(models.TsigKey)

        tsigkey = query.get(tsigkey_id)

        if not tsigkey:
            raise exceptions.TsigKeyNotFound(tsigkey_id)
        else:
            return tsigkey

    def get_tsigkey(self, context, tsigkey_id):
        tsigkey = self._get_tsigkey(context, tsigkey_id)

        return dict(tsigkey)

    def update_tsigkey(self, context, tsigkey_id, values):
        tsigkey = self._get_tsigkey(context, tsigkey_id)

        tsigkey.update(values)

        try:
            tsigkey.save(self.session)
        except exceptions.Duplicate:
            raise exceptions.DuplicateTsigKey()

        return dict(tsigkey)

    def delete_tsigkey(self, context, tsigkey_id):
        tsigkey = self._get_tsigkey(context, tsigkey_id)

        tsigkey.delete(self.session)

    # Domain Methods
    def create_domain(self, context, values):
        domain = models.Domain()

        domain.update(values)

        try:
            domain.save(self.session)
        except exceptions.Duplicate:
            raise exceptions.DuplicateDomain()

        return dict(domain)

    def get_domains(self, context, criterion=None):
        query = self.session.query(models.Domain)

        if criterion:
            query = query.filter_by(**criterion)

        try:
            result = query.all()
        except exc.NoResultFound:
            LOG.debug('No results found')
            return []
        else:
            return [dict(o) for o in result]

    def _get_domain(self, context, domain_id):
        query = self.session.query(models.Domain)

        domain = query.get(domain_id)

        if not domain:
            raise exceptions.DomainNotFound(domain_id)
        else:
            return domain

    def get_domain(self, context, domain_id):
        domain = self._get_domain(context, domain_id)

        return dict(domain)

    def find_domain(self, context, criterion):
        query = self.session.query(models.Domain)

        try:
            domain = query.filter_by(**criterion).one()
        except (exc.NoResultFound, exc.MultipleResultsFound):
            raise exceptions.DomainNotFound()
        else:
            return dict(domain)

    def update_domain(self, context, domain_id, values):
        domain = self._get_domain(context, domain_id)

        domain.update(values)

        try:
            domain.save(self.session)
        except exceptions.Duplicate:
            raise exceptions.DuplicateDomain()

        return dict(domain)

    def delete_domain(self, context, domain_id):
        domain = self._get_domain(context, domain_id)

        domain.delete(self.session)

    # Record Methods
    def create_record(self, context, domain_id, values):
        record = models.Record()

        record.update(values)
        record.domain_id = domain_id

        record.save(self.session)

        return dict(record)

    def get_records(self, context, domain_id, criterion=None):
        domain = self._get_domain(context, domain_id)

        query = domain.records

        if criterion:
            query = query.filter_by(**criterion)

        return [dict(o) for o in query.all()]

    def _get_record(self, context, record_id):
        query = self.session.query(models.Record)

        record = query.get(record_id)

        if not record:
            raise exceptions.RecordNotFound(record_id)
        else:
            return record

    def get_record(self, context, record_id):
        record = self._get_record(context, record_id)

        return dict(record)

    def find_record(self, context, domain_id, criterion):
        domain = self._get_domain(context, domain_id)

        query = domain.records

        try:
            record = query.filter_by(**criterion).one()
        except (exc.NoResultFound, exc.MultipleResultsFound):
            raise exceptions.RecordNotFound()
        else:
            return dict(record)

    def update_record(self, context, record_id, values):
        record = self._get_record(context, record_id)

        record.update(values)

        record.save(self.session)

        return dict(record)

    def delete_record(self, context, record_id):
        record = self._get_record(context, record_id)

        record.delete(self.session)

    def ping(self, context):
        start_time = time.time()

        try:
            result = self.engine.execute('SELECT 1').first()
        except:
            status = False
        else:
            status = True if result[0] == 1 else False

        return {
            'status': status,
            'rtt': "%f" % (time.time() - start_time)
        }
