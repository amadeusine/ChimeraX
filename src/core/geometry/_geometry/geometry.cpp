#include <iostream>			// use std::cerr for debugging
#include <Python.h>			// use PyObject

#include "distancespy.h"		// use py_distances_from_origin, ...
#include "spline.h"			// use natural_cubic_spline
#include "transform.h"			// use affine_transform_vertices, ...
#include "vector_ops.h"			// use inner_product_64

namespace Geometry_Cpp
{

// ----------------------------------------------------------------------------
//
static struct PyMethodDef geometry_cpp_methods[] =
{

  /* distancepy.h */
  {const_cast<char*>("distances_from_origin"), py_distances_from_origin,	METH_VARARGS, NULL},
  {const_cast<char*>("distances_perpendicular_to_axis"), py_distances_perpendicular_to_axis,	METH_VARARGS, NULL},
  {const_cast<char*>("distances_parallel_to_axis"), py_distances_parallel_to_axis,	METH_VARARGS, NULL},
  {const_cast<char*>("maximum_norm"), (PyCFunction)py_maximum_norm, METH_VARARGS|METH_KEYWORDS, NULL},

  /* spline.h */
  {const_cast<char*>("natural_cubic_spline"), (PyCFunction)natural_cubic_spline,
   METH_VARARGS|METH_KEYWORDS, NULL},

  /* transform.h */
  {const_cast<char*>("scale_and_shift_vertices"), scale_and_shift_vertices, METH_VARARGS, NULL},
  {const_cast<char*>("scale_vertices"), scale_vertices, METH_VARARGS, NULL},
  {const_cast<char*>("shift_vertices"), shift_vertices, METH_VARARGS, NULL},
  {const_cast<char*>("affine_transform_vertices"), affine_transform_vertices, METH_VARARGS, NULL},

  /* vector_ops.h */
  {const_cast<char*>("inner_product_64"), (PyCFunction)inner_product_64,
   METH_VARARGS|METH_KEYWORDS},

  {NULL, NULL, 0, NULL}
};

struct module_state {
    PyObject *error;
};

#define GETSTATE(m) ((Geometry_Cpp::module_state*)PyModule_GetState(m))

static int geometry_cpp_traverse(PyObject *m, visitproc visit, void *arg) {
    Py_VISIT(GETSTATE(m)->error);
    return 0;
}

static int geometry_cpp_clear(PyObject *m) {
    Py_CLEAR(GETSTATE(m)->error);
    return 0;
}


static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "_geometry",
        NULL,
        sizeof(struct module_state),
        geometry_cpp_methods,
        NULL,
        geometry_cpp_traverse,
        geometry_cpp_clear,
        NULL
};

}	// Geometry_Cpp namespace

// ----------------------------------------------------------------------------
// Initialization routine called by python when module is dynamically loaded.
//
PyMODINIT_FUNC
PyInit__geometry(void)
{
    PyObject *module = PyModule_Create(&Geometry_Cpp::moduledef);
    
    if (module == NULL)
      return NULL;
    Geometry_Cpp::module_state *st = GETSTATE(module);

    st->error = PyErr_NewException("_geometry.Error", NULL, NULL);
    if (st->error == NULL) {
        Py_DECREF(module);
        return NULL;
    }

    return module;
}
