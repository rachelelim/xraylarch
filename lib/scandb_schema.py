#!/usr/bin/env python
"""
SQLAlchemy wrapping of scan database

Main Class for full Database:  ScanDB
"""
import os
import time
from datetime import datetime

# from utils import backup_versions, save_backup

from sqlalchemy import (MetaData, and_, create_engine, text, func,
                        Table, Column, ColumnDefault, ForeignKey,
                        Integer, Float, String, Text, DateTime)

from sqlalchemy.orm import sessionmaker, mapper, clear_mappers, relationship
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.pool import SingletonThreadPool

# needed for py2exe?
from sqlalchemy.dialects import sqlite, mysql, postgresql

## status states for commands
CMD_STATUS = ('unknown', 'requested', 'canceled', 'starting', 'running',
               'aborting', 'stopping', 'aborted', 'finished')

PV_TYPES = (('numeric', 'Numeric Value'),
            ('enum',  'Enumeration Value'),
            ('string',  'String Value'),
            ('motor', 'Motor Value') )

def hasdb_pg(dbname, create=False,
             user='', password='', host='', port=5432):
    """
    return whether a database is known to the postgresql server,
    optionally creating (but leaving it empty) said database.
    """
    dbname = dbname.lower()
    conn_str= 'postgresql://%s:%s@%s:%i/%s'
    query = "select datname from pg_database"
    engine = create_engine(conn_str % (user, password,
                                       host, port, 'postgres'))
    conn = engine.connect()
    conn.execute("commit")
    dbs = [i[0] for i in conn.execute(query).fetchall()]
    if create and dbname not in dbs:
        conn.execute("create database %s" % dbname)
        conn.execute("commit")
    dbs = [i[0] for i in conn.execute(query).fetchall()]
    conn.close()
    return dbname in dbs

def get_dbengine(dbname, server='sqlite', create=False,
                user='', password='',  host='', port=None):
    """create databse engine"""
    if server == 'sqlite':
        return create_engine('sqlite:///%s' % (dbname),
                             poolclass=SingletonThreadPool)
    elif server == 'mysql':
        conn_str= 'mysql+mysqldb://%s:%s@%s:%i/%s'
        if port is None:
            port = 3306
        return create_engine(conn_str % (user, password, host, port, dbname))

    elif server.startswith('p'):
        conn_str= 'postgresql://%s:%s@%s:%i/%s'
        if port is None:
            port = 5432
        hasdb = hasdb_pg(dbname, create=create, user=user, password=password,
                         host=host, port=port)
        return create_engine(conn_str % (user, password, host, port, dbname))


def IntCol(name, **kws):
    return Column(name, Integer, **kws)

def ArrayCol(name,  server='sqlite', **kws):
    ArrayType = Text
    if server.startswith('post'):
        ArrayType = postgresql.ARRAY(Float)
    return Column(name, ArrayType, **kws)

def StrCol(name, size=None, **kws):
    val = Text
    if size is not None:
        val = String(size)
    return Column(name, val, **kws)

def PointerCol(name, other=None, keyid='id', **kws):
    if other is None:
        other = name
    return Column("%s_%s" % (name, keyid), None,
                  ForeignKey('%s.%s' % (other, keyid)), **kws)

def NamedTable(tablename, metadata, keyid='id', nameid='name',
               name=True, notes=True, with_pv=False, with_use=False, cols=None):
    args  = [Column(keyid, Integer, primary_key=True)]
    if name:
        args.append(StrCol(nameid, size=512, nullable=False, unique=True))
    if notes:
        args.append(StrCol('notes'))
    if with_pv:
        args.append(StrCol('pvname', size=128))
    if with_use:
        args.append(IntCol('use', default=1))
    if cols is not None:
        args.extend(cols)
    return Table(tablename, metadata, *args)

class _BaseTable(object):
    "generic class to encapsulate SQLAlchemy table"
    def __repr__(self):
        name = self.__class__.__name__
        fields = ['%s' % getattr(self, 'name', 'UNNAMED')]
        return "<%s(%s)>" % (name, ', '.join(fields))

class Info(_BaseTable):
    "general information table (versions, etc)"
    keyname, value, modify_time = None, None, None

class Status(_BaseTable):
    "status table"
    name, notes = None, None

class ScanPositioners(_BaseTable):
    "positioners table"
    name, notes, drivepv, readpv = [None]*4
    use = 1

class SlewScanPositioners(_BaseTable):
    "positioners table for slew scans"
    name, notes, drivepv, readpv = [None]*4
    use = 1


class ScanCounters(_BaseTable):
    "counters table"
    name, notes, pvname = [None]*3
    use = 1

class ScanDetectors(_BaseTable):
    "detectors table"
    name, notes, pvname, kind, options = [None]*5
    use = 1

class ScanDefs(_BaseTable):
    "scandefs table"
    name, notes, text, modify_time, last_used_time = [None]*5

class PVTypes(_BaseTable):
    "pvtype table"
    name, notes = None, None

class PVs(_BaseTable):
    "pv table"
    name, notes = None, None
    is_monitor = 0

class MonitorValues(_BaseTable):
    "monitor PV Values table"
    id, modify_time, value = None, None, None

class Macros(_BaseTable):
    "table of pre-defined macros"
    name, notes, arguments, text, output = None, None, None, None, None

class Commands(_BaseTable):
    "commands-to-be-executed table"
    command, notes, arguments = None, None, None
    status, status_name = None, None
    scandef, scandefs_id = None, None
    request_time, start_time, modify_time = None, None, None
    output_value, output_file = None, None

    def __repr__(self):
        name = self.__class__.__name__
        fields = ['%s' % getattr(self, 'command', 'Unknown')]
        return "<%s(%s)>" % (name, ', '.join(fields))

class ScanData(_BaseTable):
    notes, data, breakpoints, modify_time = [None]*4

class Instruments(_BaseTable):
    "instrument table"
    name, notes = None, None

class Positions(_BaseTable):
    "position table"
    pvs, date, name, notes = None, None, None, None
    instrument, instrument_id = None, None

class Position_PV(_BaseTable):
    "position-pv join table"
    name, notes, pv, value = None, None, None, None
    def __repr__(self):
        name = self.__class__.__name__
        fields = ['%s=%s' % (getattr(self, 'pv', '?'),
                             getattr(self, 'value', '?'))]
        return "<%s(%s)>" % (name, ', '.join(fields))

class Instrument_PV(_BaseTable):
    "intruemnt-pv join table"
    name, id, instrument, pv, display_order = None, None, None, None, None
    def __repr__(self):
        name = self.__class__.__name__
        fields = ['%s/%s' % (getattr(getattr(self, 'instrument', '?'),'name','?'),
                             getattr(getattr(self, 'pv', '?'), 'name', '?'))]
        return "<%s(%s)>" % (name, ', '.join(fields))

class Instrument_Precommands(_BaseTable):
    "instrument precommand table"
    name, notes = None, None

class Instrument_Postcommands(_BaseTable):
    "instrument postcommand table"
    name, notes = None, None

def create_scandb(dbname, server='sqlite', create=True, **kws):
    """Create a ScanDB:

    arguments:
    ---------
    dbname    name of database (filename for sqlite server)

    options:
    --------
    server    type of database server ([sqlite], mysql, postgresql)
    host      host serving database   (mysql,postgresql only)
    port      port number for database (mysql,postgresql only)
    user      user name for database (mysql,postgresql only)
    password  password for database (mysql,postgresql only)
    """

    engine  = get_dbengine(dbname, server=server, create=create, **kws)
    metadata =  MetaData(engine)
    info = Table('info', metadata,
                 Column('keyname', Text, primary_key=True, unique=True),
                 StrCol('value'),
                 Column('modify_time', DateTime, default=datetime.now),
                 Column('create_time', DateTime, default=datetime.now))

    status = NamedTable('status', metadata)
    slewpos    = NamedTable('slewscanpositioners', metadata, with_use=True,
                            cols=[StrCol('drivepv', size=128),
                                  StrCol('readpv',  size=128)])

    pos    = NamedTable('scanpositioners', metadata, with_use=True,
                        cols=[StrCol('drivepv', size=128),
                              StrCol('readpv',  size=128)])
    cnts   = NamedTable('scancounters', metadata, with_pv=True, with_use=True)
    det    = NamedTable('scandetectors', metadata, with_pv=True, with_use=True,
                        cols=[StrCol('kind',   size=128),
                              StrCol('options', size=2048)])

    scans = NamedTable('scandefs', metadata,
                       cols=[StrCol('text', size=2048),
                             Column('modify_time', DateTime),
                             Column('last_used_time', DateTime)])

    macros = NamedTable('macros', metadata,
                        cols=[StrCol('arguments'),
                              StrCol('text'),
                              StrCol('output')])

    cmds = NamedTable('commands', metadata, name=False,
                      cols=[StrCol('command'),
                            StrCol('arguments'),
                            PointerCol('status', default=1),
                            PointerCol('scandefs'),
                            Column('request_time', DateTime,
                                   default=datetime.now),
                            Column('start_time',    DateTime),
                            Column('modify_time',   DateTime,
                                   default=datetime.now),
                            StrCol('output_value'),
                            StrCol('output_file')])

    pvtypes = NamedTable('pvtypes', metadata)
    pv      = NamedTable('pvs', metadata,
                         cols=[PointerCol('pvtypes'),
                               Column('is_monitor', Integer, default=0)])

    monvals = Table('monitorvalues', metadata,
                    Column('id', Integer, primary_key=True),
                    PointerCol('pvs'),
                    StrCol('value'),
                    Column('modify_time', DateTime))


    scandata = NamedTable('scandata', metadata,
                         cols = [PointerCol('commands'),
                                 ArrayCol('data', server=server),
                                 StrCol('breakpoints', default=''),
                                 Column('modify_time', DateTime)])

    instrument = NamedTable('instruments', metadata,
                            cols=[Column('show', Integer, default=1),
                                  Column('display_order', Integer, default=0)])

    position  = NamedTable('positions', metadata,
                           cols=[Column('modify_time', DateTime),
                                 PointerCol('instruments')])

    instrument_precommand = NamedTable('instrument_precommands', metadata,
                                       cols=[Column('exec_order', Integer),
                                             PointerCol('commands'),
                                             PointerCol('instruments')])

    instrument_postcommand = NamedTable('instrument_postcommands', metadata,
                                        cols=[Column('exec_order', Integer),
                                              PointerCol('commands'),
                                              PointerCol('instruments')])

    instrument_pv = Table('instrument_pv', metadata,
                          Column('id', Integer, primary_key=True),
                          PointerCol('instruments'),
                          PointerCol('pvs'),
                          Column('display_order', Integer, default=0))


    position_pv = Table('position_pv', metadata,
                        Column('id', Integer, primary_key=True),
                        StrCol('notes'),
                        PointerCol('positions'),
                        PointerCol('pvs'),
                        StrCol('value'))

    metadata.create_all()

    session = sessionmaker(bind=engine)()

    # add some initial data:
    scans.insert().execute(name='NULL', text='')

    for name in CMD_STATUS:
        status.insert().execute(name=name)

    for name, notes in PV_TYPES:
        pvtypes.insert().execute(name=name, notes=notes)

    for keyname, value in (("version", "1.0"),
                           ("user_name", ""),
                           ("experiment_id",  ""),
                           ("user_folder",    ""),
                           ("request_command_abort", "0"),
                           ("request_command_pause", "0"),
                           ("request_command_resume", "0"),
                           ("request_shutdown", "0") ):
        info.insert().execute(keyname=keyname, value=value)
    session.commit()

def map_scandb(metadata):
    """set up mapping of SQL metadata and classes
    returns two dictionaries, tables and classes
    each with entries
    tables:    {tablename: table instance}
    classes:   {tablename: table class}

    """
    tables = metadata.tables
    classes = {}
    try:
        clear_mappers()
    except:
        pass
    for cls in (Info, Status, PVTypes, PVs, MonitorValues, Macros,
                Commands, ScanData, ScanPositioners, ScanCounters,
                ScanDetectors, ScanDefs, SlewScanPositioners,
                Positions, Position_PV, Instruments, Instrument_PV,
                Instrument_Precommands, Instrument_Postcommands):

        name = cls.__name__.lower()
        props = {}
        if name == 'commands':
            props = {'status': relationship(Status),
                     'scandefs': relationship(ScanDefs)}
        elif name == 'scandata':
            props = {'commands': relationship(Commands)}
        elif name == 'monitorvalues':
            props = {'pv': relationship(PVs)}
        elif name == 'pvs':
            props = {'pvtype': relationship(PVTypes)}
        elif name == 'instruments':
            properties={'pvs': relationship(PVs,
                                            backref='instruments',
                                            secondary=tables['instrument_pv'])}
        elif name == 'positions':
            properties={'instrument': relationship(Instruments,
                                            backref='positions'),
                        'pvs': relationship(Position_PV)}
        elif name == 'instrument_pv':
            properties={'pv': relationship(PVs),
                        'instrument': relationship(Instruments)}
        elif name == 'position_pv':
            properties={'pv': relationship(PVs)}
        elif name == 'instrument_precommands':
            properties={'instrument': relationship(Instruments,
                                                   backref='precommands'),
                        'command': relationship(Commands)}
        elif name == 'instrument_postcommands':
            properties={'instrument': relationship(Instruments,
                                                   backref='postcommands'),
                        'command': relationship(Commands)}

        mapper(cls, tables[name], properties=props)
        classes[name] = cls


    # set onupdate and default constraints for several datetime columns
    # note use of ColumnDefault to wrap onpudate/default func
    fnow = ColumnDefault(datetime.now)
    for tname in ('info', 'commands', 'positions','scandefs', 'scandata',
                  'monitorvalues', 'commands'):
        tables[tname].columns['modify_time'].onupdate =  fnow
        tables[tname].columns['modify_time'].default =  fnow

    for tname, cname in (('info', 'create_time'),
                         ('commands', 'request_time')):
        tables[tname].columns[cname].default = fnow
    return tables, classes
