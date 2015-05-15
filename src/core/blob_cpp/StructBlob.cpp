// vi: set expandtab ts=4 sw=4:
#include "StructBlob.h"
#include "AtomBlob.h"
#include "BondBlob.h"
#include "PseudoBlob.h"
#include "ResBlob.h"
#include <atomstruct/Bond.h>
#include "numpy_common.h"
#include "blob_op.h"
#include "set_blob.h"
#include <unordered_map>
#include <stddef.h>

namespace blob {

using atomstruct::AtomicStructure;
using atomstruct::Atom;
using atomstruct::Bond;
    
template PyObject* new_blob<StructBlob>(PyTypeObject*);

extern "C" {
    
static void
StructBlob_dealloc(PyObject* obj)
{
    StructBlob* self = static_cast<StructBlob*>(obj);
    delete self->_observer;
    delete self->_items;
    if (self->_weaklist)
        PyObject_ClearWeakRefs(obj);
    obj->ob_type->tp_free(obj);
}

static const char StructBlob_doc[] = "StructBlob documentation";

static PyObject*
sb_pointers(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    if (PyArray_API == NULL)
        import_array1(NULL); // initialize NumPy
    unsigned int shape[1] = {(unsigned int)sb->_items->size()};
    PyObject* ptrs = allocate_python_array(1, shape, NPY_UINTP);
    void **p = (void **) PyArray_DATA((PyArrayObject*)ptrs);
    for (auto s: *(sb->_items))
      *p++ = s.get();
    return ptrs;
}

static PyObject*
sb_atoms(PyObject* self, void*)
{
    PyObject* py_ab = new_blob<AtomBlob>(&AtomBlob_type);
    AtomBlob* ab = static_cast<AtomBlob*>(py_ab);
    StructBlob* sb = static_cast<StructBlob*>(self);
    for (auto& as: *sb->_items)
        for (auto& a: as->atoms()) 
            ab->_items->emplace_back(a.get());
    return py_ab;
}

static PyObject*
sb_ball_scales(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    if (PyArray_API == NULL)
        import_array1(NULL); // initialize NumPy
    static_assert(sizeof(unsigned int) >= 4, "need 32-bit ints");
    unsigned int shape[1] = {(unsigned int)sb->_items->size()};
    PyObject* ball_scales = allocate_python_array(1, shape, NPY_FLOAT);
    unsigned char* data = (unsigned char*) PyArray_DATA((PyArrayObject*)ball_scales);
    for (auto s: *(sb->_items)) {
        *data++ = s->ball_scale();
    }
    return ball_scales;
}

static int
sb_set_ball_scales(PyObject* self, PyObject* value, void*)
{
    return set_blob<StructBlob>(self, value,
        &atomstruct::AtomicStructure::set_ball_scale);
}

static PyObject*
sb_bonds(PyObject* self, void*)
{
    PyObject* py_bb = new_blob<BondBlob>(&BondBlob_type);
    BondBlob* bb = static_cast<BondBlob*>(py_bb);
    StructBlob* sb = static_cast<StructBlob*>(self);
    for (auto& as: *sb->_items)
        for (auto& b: as->bonds()) 
            bb->_items->emplace_back(b.get());
    return py_bb;
}

static PyObject*
sb_displays(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    if (PyArray_API == NULL)
        import_array1(NULL); // initialize NumPy
    static_assert(sizeof(unsigned int) >= 4, "need 32-bit ints");
    unsigned int shape[1] = {(unsigned int)sb->_items->size()};
    PyObject* displays = allocate_python_array(1, shape, NPY_BOOL);
    unsigned char* data = (unsigned char*) PyArray_DATA((PyArrayObject*)displays);
    for (auto s: *(sb->_items)) {
        *data++ = s->display();
    }
    return displays;
}

static int
sb_set_displays(PyObject* self, PyObject* value, void*)
{
    return set_blob<StructBlob>(self, value,
        &atomstruct::AtomicStructure::set_display);
}

static PyObject*
sb_num_atoms(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    size_t num_atoms = 0;
    for (auto s: *(sb->_items)) {
        num_atoms += s->num_atoms();
    }
    return PyLong_FromSize_t(num_atoms);
}

static PyObject*
sb_num_bonds(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    size_t num_bonds = 0;
    for (auto s: *(sb->_items)) {
        num_bonds += s->num_bonds();
    }
    return PyLong_FromSize_t(num_bonds);
}

static PyObject*
sb_num_hyds(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    size_t num_hyds = 0;
    for (auto s: *(sb->_items)) {
        num_hyds += s->num_hyds();
    }
    return PyLong_FromSize_t(num_hyds);
}

static PyObject*
sb_num_residues(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    size_t num_residues = 0;
    for (auto s: *(sb->_items)) {
        num_residues += s->num_residues();
    }
    return PyLong_FromSize_t(num_residues);
}

static PyObject*
sb_num_chains(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    size_t num_chains = 0;
    for (auto s: *(sb->_items)) {
        num_chains += s->num_chains();
    }
    return PyLong_FromSize_t(num_chains);
}

static PyObject*
sb_num_coord_sets(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    size_t num_coord_sets = 0;
    for (auto s: *(sb->_items)) {
        num_coord_sets += s->num_coord_sets();
    }
    return PyLong_FromSize_t(num_coord_sets);
}

static PyObject*
sb_pbg_map(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    if (sb->_items->size() > 1) {
        PyErr_SetString(PyExc_ValueError,
            "'pbg_map' attr only for single-structure blobs."
            "  Use 'structures' attr to get single-structure blobs.");
        return NULL;
    }
    PyObject* pbg_map = PyDict_New();
    if (pbg_map == NULL)
        return NULL;
    if (sb->_items->size() == 0)
        return pbg_map;
    auto structure = *(sb->_items->begin());
    for (auto grp_info: structure->pb_mgr().group_map()) {
        PyObject* name = PyUnicode_FromString(grp_info.first.c_str());
        if (name == NULL)
            return NULL;
        PyObject* py_pblob = new_blob<PseudoBlob>(&PseudoBlob_type);
        if (py_pblob == NULL)
            return NULL;
        for (auto pb: grp_info.second->pseudobonds()) {
            static_cast<PseudoBlob*>(py_pblob)->_items->emplace_back(pb);
        }
        PyDict_SetItem(pbg_map, name, py_pblob);
    }
    return pbg_map;
}

static PyObject*
sb_residues(PyObject* self, void*)
{
    PyObject* py_rb = new_blob<ResBlob>(&ResBlob_type);
    ResBlob* rb = static_cast<ResBlob*>(py_rb);
    StructBlob* sb = static_cast<StructBlob*>(self);
    for (auto si = sb->_items->begin(); si != sb->_items->end(); ++si) {
        const AtomicStructure::Residues& residues = (*si).get()->residues();
        for (auto ri = residues.begin(); ri != residues.end(); ++ri)
            rb->_items->emplace_back((*ri).get());
    }
    return py_rb;
}

static PyObject*
sb_structures(PyObject* self, void*)
{
    StructBlob* sb = static_cast<StructBlob*>(self);
    PyObject* struct_list = PyList_New(sb->_items->size());
    if (struct_list == NULL)
        return NULL;
    StructBlob::ItemsType::size_type i = 0;
    for (auto si = sb->_items->begin(); si != sb->_items->end(); ++si) {
        PyObject* py_single_sb = new_blob<StructBlob>(&StructBlob_type);
        PyList_SET_ITEM(struct_list, i++, py_single_sb);
        StructBlob* single_sb = static_cast<StructBlob*>(py_single_sb);
        // since it's a shared_ptr, push_back, not emplace_back...
        single_sb->_items->push_back(*si);
    }
    return struct_list;
}

static PyMethodDef StructBlob_methods[] = {
    { (char*)"filter", blob_filter<StructBlob>, METH_O,
        (char*)"filter structure blob based on array/list of booleans" },
    { (char*)"intersect", blob_intersect<StructBlob>, METH_O,
        (char*)"intersect structure blobs" },
    { (char*)"merge", blob_merge<StructBlob>, METH_O,
        (char*)"merge atom blobs" },
    { (char*)"subtract", blob_subtract<StructBlob>, METH_O,
        (char*)"subtract atom blobs" },
    { NULL, NULL, 0, NULL }
};

static PyNumberMethods StructBlob_as_number = {
    0,                                      // nb_add
    (binaryfunc)blob_subtract<StructBlob>,  // nb_subtract
    0,                                      // nb_multiply
    0,                                      // nb_remainder
    0,                                      // nb_divmod
    0,                                      // nb_power
    0,                                      // nb_negative
    0,                                      // nb_positive
    0,                                      // nb_absolute
    0,                                      // nb_bool
    0,                                      // nb_invert
    0,                                      // nb_lshift
    0,                                      // nb_rshift
    (binaryfunc)blob_intersect<StructBlob>, // nb_and
    0,                                      // nb_xor
    (binaryfunc)blob_merge<StructBlob>,     // nb_or
    0,                                      // nb_int
    0,                                      // nb_reserved
    0,                                      // nb_float
    0,                                      // nb_inplace_add
    0,                                      // nb_inplace_subtract
    0,                                      // nb_inplace_multiply
    0,                                      // nb_inplace_remainder
    0,                                      // nb_inplace_power
    0,                                      // nb_inplace_lshift
    0,                                      // nb_inplace_rshift
    0,                                      // nb_inplace_and
    0,                                      // nb_inplace_xor
    0,                                      // nb_inplace_or
};

static PyGetSetDef StructBlob_getset[] = {
    { (char*)"_struct_pointers", sb_pointers, NULL,
        (char*)"numpy array of atomic structure pointers", NULL},
    { (char*)"atoms", sb_atoms, NULL,
        (char*)"AtomBlob", NULL},
    { (char*)"ball_scales", sb_ball_scales, sb_set_ball_scales,
        (char*)"numpy array of (float) ball scales", NULL},
    { (char*)"bonds", sb_bonds, NULL,
        (char*)"BondBlob", NULL},
    { (char*)"displays", sb_displays, sb_set_displays,
        (char*)"numpy array of (bool) displays", NULL},
    { (char*)"num_atoms", sb_num_atoms, NULL,
        (char*)"number of atoms", NULL},
    { (char*)"num_bonds", sb_num_bonds, NULL,
        (char*)"number of bonds", NULL},
    { (char*)"num_hyds", sb_num_hyds, NULL,
        (char*)"number of hydrogens", NULL},
    { (char*)"num_residues", sb_num_residues, NULL,
        (char*)"number of residues", NULL},
    { (char*)"num_chains", sb_num_chains, NULL,
        (char*)"number of chains", NULL},
    { (char*)"num_coord_sets", sb_num_coord_sets, NULL,
        (char*)"number of coord sets", NULL},
    { (char*)"pbg_map", sb_pbg_map, NULL,
        (char*)"dict keyed on pb group name, value = group blob", NULL},
    { (char*)"structures", sb_structures, NULL,
        (char*)"list of one-structure-model StructBlobs", NULL},
    { (char*)"residues", sb_residues, NULL,
        (char*)"ResBlob", NULL},
    { NULL, NULL, NULL, NULL, NULL }
};

static PyMappingMethods StructBlob_len = { blob_len<StructBlob>, NULL, NULL };

} // extern "C"

PyTypeObject StructBlob_type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "structaccess.StructBlob", // tp_name
    sizeof (StructBlob), // tp_basicsize
    0, // tp_itemsize
    StructBlob_dealloc, // tp_dealloc
    0, // tp_print
    0, // tp_getattr
    0, // tp_setattr
    0, // tp_reserved
    0, // tp_repr
    &StructBlob_as_number, // tp_as_number
    0, // tp_as_sequence
    &StructBlob_len, // tp_as_mapping
    0, // tp_hash
    0, // tp_call
    0, // tp_str
    0, // tp_getattro
    0, // tp_setattro
    0, // tp_as_buffer
    Py_TPFLAGS_DEFAULT, // tp_flags
    StructBlob_doc, // tp_doc
    0, // tp_traverse
    0, // tp_clear
    0, // tp_richcompare
    //sizeof(PyObject), // tp_weaklistoffset
    offsetof(StructBlob, _weaklist), // tp_weaklistoffset
    0, // tp_iter
    0, // tp_iternext
    StructBlob_methods, // tp_methods
    0, // tp_members
    StructBlob_getset, // tp_getset
    0, // tp_base
    0, // tp_dict
    0, // tp_descr_get
    0, // tp_descr_set
    0, // tp_dict_offset
    0, // tp_init,
    PyType_GenericAlloc, // tp_alloc
    0, // tp_new
    PyObject_Free, // tp_free
    0, // tp_is_gc
    0, // tp_bases
    0, // tp_mro
    0, // tp_cache
    0, // tp_subclasses
    0, // tp_weaklist
};

}  // namespace blob
